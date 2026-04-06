import uuid

from django.conf import settings
from django.db import models


class Media(models.Model):
    """
    Represents a model for managing media files and their metadata.

    This class is used to store information about media files, such as the type of media,
    its S3 storage key, the user who uploaded it, the file metadata, and the upload status.
    It can handle both images and videos, and tracks the status of the upload process.

    :ivar id: Unique identifier for the media object.
    :type id: UUID

    :ivar uploaded_by: Reference to the user who uploaded the media file.
    :type uploaded_by: ForeignKey

    :ivar s3_key: The S3 object key (path within the bucket).
    :type s3_key: str

    :ivar media_type: The type of media (e.g., image, video).
    :type media_type: str

    :ivar content_type: The MIME type of the media file, e.g., image/jpeg.
    :type content_type: str

    :ivar file_name: Original filename of the media file provided by the client.
    :type file_name: str

    :ivar file_size: Size of the media file in bytes. Can be null or blank if not available.
    :type file_size: int

    :ivar upload_status: Current status of the file upload process (e.g., pending,
        completed, failed).
    :type upload_status: str

    :ivar created_at: Timestamp indicating when the media object was created.
    :type created_at: datetime

    :ivar updated_at: Timestamp indicating the last time the media object was updated.
    :type updated_at: datetime
    """

    class MediaType(models.TextChoices):
        """
        Represents a set of media type choices.

        Provides enumerations for different types of media, such as images and videos.
        This can be used in contexts where specifying a type of media is required.

        :ivar IMAGE: Represents an image media type.
        :type IMAGE: str
        :ivar VIDEO: Represents a video media type.
        :type VIDEO: str
        """

        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class UploadStatus(models.TextChoices):
        """
        Represents the status of an upload process.

        This class is a Django model TextChoices enumeration used to define and
        represent the allowed states of an upload operation, such as when a
        pre-signed URL is generated but the upload has not been completed,
        when an upload is successfully completed, or when an upload attempt has
        failed. It provides a structured way to handle these states consistently
        across the application.

        :ivar PENDING: Indicates that a pre-signed URL has been generated,
                       but the upload process has not been completed.
        :type PENDING: str
        :ivar COMPLETED: Indicates that the upload process has been successfully
                         completed.
        :type COMPLETED: str
        :ivar FAILED: Indicates that the upload process has failed.
        :type FAILED: str
        """

        PENDING = "pending", "Pending"  # presigned-url generated, upload not done
        COMPLETED = "completed", "Completed"  # upload completed
        FAILED = "failed", "Failed"  # upload failed

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="media_files",
    )

    s3_key = models.CharField(max_length=500, unique=True, help_text="The S3 object key (path within the bucket).")

    media_type = models.CharField(max_length=10, choices=MediaType)
    content_type = models.CharField(max_length=100, help_text="MIME type, e.g., image/jpeg")
    file_name = models.CharField(max_length=255, help_text="Original filename from the client")
    file_size = models.PositiveBigIntegerField(help_text="File size in bytes.", null=True, blank=True)
    upload_status = models.CharField(max_length=10, choices=UploadStatus, default=UploadStatus.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Represents the metadata and attributes of a media object.

        This class defines metadata and ordering for media objects in a Django model.
        It provides a description of how media should be displayed and ordered in a
        database query and administrative interface.

        :ivar verbose_name: A human-readable singular name for the media entity.
        :type verbose_name: str
        :ivar verbose_name_plural: A human-readable plural name for the media entity.
        :type verbose_name_plural: str
        :ivar ordering: Defines the default ordering for the media objects in query sets.
        :type ordering: list
        """

        verbose_name = "media"
        verbose_name_plural = "media"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """
        Converts the object to its string representation.

        The string representation includes the `media_type` and the `s3_key` attributes
        of the object, concatenated with a hyphen ('-') for easy readability.

        :return: String representation of the object.
        :rtype: str
        """
        return f"{self.media_type} - {self.s3_key}"
