from django.contrib import admin

from apps.moderation.models import Block, Mute


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    """
    Handles the administration interface for the Block model.

    The class defines how the Block model is displayed and managed in the Django
    administration interface. It customizes list displays, filtering, searching,
    and read-only fields for improved usability by administrators.
    """

    list_display = [
        "blocker",
        "blocked",
        "created_at",
    ]
    list_filter = [
        "created_at",
    ]
    search_fields = [
        "blocker__username",
        "blocker__email",
        "blocked__username",
        "blocked__email",
    ]
    readonly_fields = [
        "id",
        "created_at",
    ]
    raw_id_fields = [
        "blocker",
        "blocked",
    ]


@admin.register(Mute)
class MuteAdmin(admin.ModelAdmin):
    """
    Provides an admin interface for managing `Mute` model objects.

    This class defines a Django admin configuration for the `Mute` model,
    allowing administrators to manage mute relationships between users through
    the admin panel. It provides functionality to display, filter, and search
    the mute records effectively.
    """

    list_display = [
        "muter",
        "muted",
        "created_at",
    ]
    list_filter = [
        "created_at",
    ]
    search_fields = [
        "muter__username",
        "muter__email",
        "muted__username",
        "muted__email",
    ]
    readonly_fields = [
        "id",
        "created_at",
    ]
    raw_id_fields = [
        "muter",
        "muted",
    ]
