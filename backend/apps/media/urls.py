from django.urls import path

from . import views

app_name = "media"

urlpatterns = [
    path(
        "presign/upload/",
        views.PresignUploadView.as_view(),
        name="presign-upload",
    ),
    path(
        "confirm-upload/",
        views.ConfirmUploadView.as_view(),
        name="confirm-upload",
    ),
    path("<uuid:pk>/", views.MediaDetailView.as_view(), name="media-detail"),
]
