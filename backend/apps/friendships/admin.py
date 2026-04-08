from django.contrib import admin

from apps.friendships.models import FriendRequest


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = [
        "sender",
        "receiver",
        "status",
        "created_at",
        "responded_at",
    ]
    list_filter = [
        "status",
        "created_at",
    ]
    search_fields = [
        "sender__username",
        "sender__email",
        "receiver__username",
        "receiver__email",
    ]
    readonly_fields = [
        "id",
        "created_at",
    ]
    raw_id_fields = [
        "sender",
        "receiver",
    ]
