from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("users/", views.UserListView.as_view(), name="user-list"),
    path(
        "users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"
    ),
]
