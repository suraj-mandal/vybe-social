from django.urls import path

from apps.moderation import views

app_name = "moderation"

urlpatterns = [
    # blocks
    path(
        "blocks/<uuid:user_id>/",
        views.BlockUserView.as_view(),
        name="block-user",
    ),
    path(
        "blocks/<uuid:user_id>/unblock/",
        views.UnblockUserView.as_view(),
        name="unblock-user",
    ),
    path("blocks/", views.BlockedUsersListView.as_view(), name="blocked-list"),
    # mutes
    path(
        "mutes/<uuid:user_id>/", views.MuteUserView.as_view(), name="mute-user"
    ),
    path(
        "mutes/<uuid:user_id>/unmute/",
        views.UnmuteUserView.as_view(),
        name="unmute-user",
    ),
    path("mutes/", views.MutedUsersListView.as_view(), name="muted-list"),
]
