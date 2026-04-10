from django.urls import path

from apps.moderation import views

app_name = "moderation"

urlpatterns = [
    # blocks
    path(
        "blocks/<uuid:user_id>/",
        views.UserBlockView.as_view(),
        name="block-user",
    ),
    path("blocks/", views.BlockedUsersListView.as_view(), name="blocked-list"),
    # mutes
    path(
        "mutes/<uuid:user_id>/", views.UserMuteView.as_view(), name="mute-user"
    ),
    path("mutes/", views.MutedUsersListView.as_view(), name="muted-list"),
]
