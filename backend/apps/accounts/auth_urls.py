from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

app_name = "auth"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/",
         views.ResendVerificationView.as_view(),
         name="resend-verification"),
    path(
        "password-reset/",
        views.PasswordResetRequestView.as_view(),
        name="password-reset"
    ),
    path(
        "password-reset-confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm"
    ),
    path(
        "change-password/",
        views.ChangePasswordView.as_view(),
        name="change-password"
    )
]
