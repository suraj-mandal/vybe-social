from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Profile model.

    Customizes the Django admin interface for the Profile model to control how
    profiles appear and can be interacted with in the admin panel. Provides
    functionality for listing, searching, and displaying fields, as well as
    specifying read-only fields for immutable attributes.

    :ivar list_display: List of fields to be displayed in the list view of the admin
        panel.
    :type list_display: list[str]
    :ivar search_fields: Fields available for search functionality in the admin
        panel.
    :type search_fields: list[str]
    :ivar raw_id_fields: Fields that will use raw ID widgets instead of default
        related widgets.
    :type raw_id_fields: list[str]
    :ivar readonly_fields: Fields that are displayed as read-only in the admin
        panel.
    :type readonly_fields: list[str]
    """

    list_display = ["user", "location", "created_at"]
    search_fields = ["user__username", "user__email", "location"]
    raw_id_fields = ["user"]
    readonly_fields = ["created_at", "updated_at"]
