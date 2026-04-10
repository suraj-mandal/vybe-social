from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("me/", views.CurrentUserProfileView.as_view(), name="my-profile"),
    path(
        "<str:username>/",
        views.PublicProfileDetailView.as_view(),
        name="profile-detail",
    ),
]
