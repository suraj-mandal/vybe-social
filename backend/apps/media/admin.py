from django.contrib import admin

from .models import Media


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    """
    Admin class for Media model.

    This class is used to define the administrative interface for the Media model in the Django
    admin site. It provides customization options for how Media instances are displayed, sorted,
    and filtered within the admin interface.

    :ivar list_display: Specifies the fields of the Media model to be displayed as columns
        in the admin list view. Includes:
        - id: The unique identifier of the media.
        - uploaded_by: The user who uploaded the media.
        - media_type: The type of the media (e.g., image, video).
        - upload_status: The current upload status of the media.
        - file_name: The name of the uploaded file.
        - created_at: The timestamp when the media was created.
    :type list_display: list[str]

    :ivar list_filter: Specifies the fields to display filtering options for in the
        admin interface. Includes:
        - media_type: Filter by the type of the media.
        - upload_status: Filter by the upload status of the media.
    :type list_filter: list[str]

    :ivar search_fields: Specifies which fields should be searchable in the
        admin interface. Includes:
        - s3_key: The S3 storage key for the media.
        - file_name: The name of the uploaded file.
        - uploaded_by__email: The email of the user who uploaded the media.
    :type search_fields: list[str]

    :ivar raw_id_fields: Specifies fields to be displayed with a raw ID widget for selection.
        Includes the field:
        - uploaded_by: The user who uploaded the media.
    :type raw_id_fields: list[str]

    :ivar readonly_fields: Specifies the fields that are read-only in the admin interface.
        Includes:
        - created_at: The timestamp when the media was created.
        - updated_at: The timestamp when the media was last updated.
    :type readonly_fields: list[str]
    """

    list_display = [
        "id",
        "uploaded_by",
        "media_type",
        "upload_status",
        "file_name",
        "created_at",
    ]
    list_filter = [
        "media_type",
        "upload_status",
    ]
    search_fields = ["s3_key", "file_name", "uploaded_by__email"]
    raw_id_fields = [
        "uploaded_by",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
