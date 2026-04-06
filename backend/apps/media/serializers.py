from typing import Any

from django.conf import settings
from rest_framework import serializers

from .models import Media
from .s3_service import generate_presigned_read_url


class PresignUploadSerializer(serializers.Serializer):
    """
    PresignUploadSerializer is responsible for validating file upload parameters
    and determining file classifications based on content type and size.

    This serializer checks the validity of the file upload inputs, including
    `file_name`, `content_type`, `file_size`, and `folder`. It ensures that the
    file adheres to the application's constraints for allowed content types and
    size limitations for images and videos. When validated, this serializer assigns
    a `media_type` attribute denoting whether the file is an image or a video.

    :ivar file_name: Specifies the name of the file to be uploaded.
    :type file_name: str
    :ivar content_type: Specifies the MIME type of the file to be uploaded.
    :type content_type: str
    :ivar file_size: Specifies the size of the file to be uploaded, with a minimum
        value of 1.
    :type file_size: int
    :ivar folder: Specifies the category of folder where the file will be stored.
        The value must be one of the allowed choices, such as "avatars" or "folders".
    :type folder: str
    """

    file_name = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField(min_value=1)
    folder = serializers.ChoiceField(choices=["avatars", "posts"])

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Validates the provided attributes for media upload, ensuring that the file type
        and size comply with defined constraints. Differentiates between image and
        video files, attaching appropriate metadata upon validation. Raises a validation
        error if the file does not meet the required criteria.

        :param attrs: Dictionary containing the metadata of the file being validated.
            Expected keys include:
            - "content_type" (str): MIME type of the file, indicating its format.
            - "file_size" (int): Size of the file in bytes.
        :return: A dictionary containing the validated attributes along with
            additional metadata indicating the media type.
        :rtype: dict
        :raises serializers.ValidationError: Raised if:
            - The file's content type is not in the allowed list.
            - The file size exceeds the maximum allowed size for its type.
        """
        content_type = attrs["content_type"]
        file_size = attrs["file_size"]

        # checking for size limitations of the file being uploaded
        if content_type in settings.MEDIA_ALLOWED_IMAGE_TYPES:
            if file_size > settings.MEDIA_MAX_IMAGE_SIZE:
                raise serializers.ValidationError(
                    {"file_size": f"Image must be under {settings.MEDIA_MAX_IMAGE_SIZE // (1024**2)} MB."}
                )
            attrs["media_type"] = Media.MediaType.IMAGE

        elif content_type in settings.MEDIA_ALLOWED_VIDEO_TYPES:
            if file_size > settings.MEDIA_MAX_VIDEO_SIZE:
                raise serializers.ValidationError(
                    {"file_size": f"Video must be under {settings.MEDIA_MAX_IMAGE_SIZE // (1024**2)} MB."}
                )
            attrs["media_type"] = Media.MediaType.VIDEO

        else:
            allowed_content_types = settings.MEDIA_ALLOWED_IMAGE_TYPES + settings.MEDIA_ALLOWED_VIDEO_TYPES
            raise serializers.ValidationError(
                {"content_type": f"Unsupported file type. Allowed: {', '.join(allowed_content_types)}"}
            )

        return attrs


class ConfirmUploadSerializer(serializers.Serializer):
    """
    Serializer for confirming file uploads.

    This serializer validates the necessary details required to confirm a file upload
    to an S3 storage. It includes fields for the S3 key and the file size. This ensures
    that the provided input meets the specified constraints for a successful upload
    confirmation.

    :ivar s3_key: The S3 key representing the file's location in the bucket.
    :type s3_key: str
    :ivar file_size: The size of the file in bytes. Must be greater than or equal to 1.
    :type file_size: int
    """

    s3_key = serializers.CharField(max_length=500)
    file_size = serializers.IntegerField(min_value=1)


class MediaSerializer(serializers.ModelSerializer):
    """
    Serializer class for Media objects.

    This class is used for serializing and deserializing data related to Media objects.
    It provides fields that represent the Media model attributes and adds a custom method
    field for generating a presigned URL for reading the media file.

    :ivar url: A custom method field that returns a presigned URL for accessing the media
               if the upload status is completed.
    :type url: Optional[str]
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = [
            "id",
            "s3_key",
            "media_type",
            "content_type",
            "file_name",
            "file_size",
            "upload_status",
            "url",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj: Media) -> str | None:
        """
        Retrieves the presigned URL for accessing a media object's content if its upload process has been completed.

        :param obj: The media object to retrieve a presigned URL for.
        :type obj: Media
        :return: The presigned URL as a string if the upload status is completed, otherwise None.
        :rtype: Optional[str]
        """
        if obj.upload_status != Media.UploadStatus.COMPLETED:
            return None

        return generate_presigned_read_url(obj.s3_key)
