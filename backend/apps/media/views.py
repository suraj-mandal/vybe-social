from collections.abc import Iterable
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Media
from .s3_service import (
    delete_s3_object,
    generate_presigned_upload_url,
    verify_s3_object,
)
from .serializers import (
    ConfirmUploadSerializer,
    MediaSerializer,
    PresignUploadSerializer,
)


class PresignUploadView(generics.GenericAPIView):
    serializer_class = PresignUploadSerializer
    permission_classes = [IsAuthenticated]

    def post(
        self, request: Request, *args: list[Any], **kwargs: dict[str, Any]
    ) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        presign_result = generate_presigned_upload_url(
            folder=data["folder"],
            filename=data["file_name"],
            content_type=data["content_type"],
            file_size=data["file_size"],
        )

        # create a pending MEDIA record
        # since presigned url is generated
        media = Media.objects.create(
            uploaded_by=request.user,
            s3_key=presign_result["s3_key"],
            media_type=data["media_type"],
            content_type=data["content_type"],
            file_name=data["file_name"],
            upload_status=Media.UploadStatus.PENDING,
        )

        return Response(
            {
                "upload_url": presign_result["upload_url"],
                "s3_key": presign_result["s3_key"],
                "media_id": str(media.id),
            },
            status=status.HTTP_200_OK,
        )


class ConfirmUploadView(generics.GenericAPIView):
    serializer_class = ConfirmUploadSerializer
    permission_classes = [IsAuthenticated]

    def post(
        self, request: Request, *args: list[Any], **kwargs: dict[str, Any]
    ) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        s3_key = serializer.validated_data["s3_key"]
        file_size = serializer.validated_data["file_size"]

        try:
            media = Media.objects.get(
                s3_key=s3_key,
                uploaded_by=request.user,
                upload_status=Media.UploadStatus.PENDING,
            )
        except Media.DoesNotExist:
            return Response(
                {"detail": "No pending upload found for this key."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # verify the file size with the actual file size
        try:
            verified_file_metadata = verify_s3_object(s3_key, file_size)
        except (ClientError, BotoCoreError):
            return Response(
                {"detail": "File not found in S3. Upload may have failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verified_file_metadata["verified"]:
            # Size mismatch is there, delete the orphaned S3 object and reject
            delete_s3_object(s3_key)
            media.upload_status = Media.UploadStatus.FAILED
            media.save(
                update_fields=[
                    "upload_status",
                    "updated_at",
                ]
            )
            return Response(
                {
                    "detail": "File size mismatch.",
                    "declared_size": file_size,
                    "actual_size": verified_file_metadata["actual_size"],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        media.file_size = verified_file_metadata["actual_size"]
        media.upload_status = Media.UploadStatus.COMPLETED
        media.save(
            update_fields=[
                "file_size",
                "upload_status",
                "updated_at",
            ]
        )

        return Response(
            MediaSerializer(media).data,
            status=status.HTTP_200_OK,
        )


class MediaDetailView(generics.RetrieveDestroyAPIView):
    """
    Retrieves and deletes a media instance for the authenticated user.

    This class represents a view for retrieving and deleting media objects
    associated with the authenticated user. It uses the `MediaSerializer`
    for serialization and enforces authentication through the
    `IsAuthenticated` permission class.

    :ivar serializer_class: Serializer class used for this view.
    :type serializer_class: type
    :ivar permission_classes: List of permission classes to verify.
    :type permission_classes: list
    """

    serializer_class = MediaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> Iterable[Media]:
        """
        Filters and returns a queryset of Media objects uploaded by the current user.

        :returns: An iterable containing Media objects uploaded by the user.
        :rtype: Iterable[Media]
        """
        return Media.objects.filter(uploaded_by=self.request.user)

    def perform_destroy(self, instance: Media) -> None:
        """
        Deletes a Media instance and its associated object stored in Amazon S3.

        This method first deletes the S3 object linked to the provided Media instance
        using its unique `s3_key`. Afterward, the Media instance itself is removed
        from the database.

        :param instance: The Media instance to be deleted. The instance must have a
                         valid `s3_key` linked to an object in Amazon S3.
        :type instance: Media
        :return: None
        """
        delete_s3_object(instance.s3_key)
        instance.delete()
