from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


def send_verification_email(user: User) -> None:
    """
    Sends a verification email to the specified user. This email includes a personalized
    link that allows the user to verify their email address. The generated link comprises
    a unique user identifier and a secure token.

    :param user: User object representing the account that requires email verification.
    :return: None
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    verification_link = f"{settings.FRONTEND_URL}/verify/{uid}/{token}/"

    send_mail(
        subject="Vybe - Verify your email address",
        message=(
            f"Hi {user.username}, \n\n"
            f"Please verify your email by clicking the link below:\n\n"
            f"{verification_link}\n\n"
            f"If you didn't create an account, ignore this email.\n\n"
            f"- The Vybe Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def send_password_reset_email(user: User) -> None:
    """
    Sends a password reset email to the specified user.

    This function generates a secure token and a unique identifier for the user,
    constructs a password reset link, and sends an email to the user's registered
    email address containing the reset link. The reset link has an expiration
    time defined by the application's settings.

    :param user: The user object for whom the password reset email is being sent.
    :type user: User
    :return: None
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"

    send_mail(
        subject="Vybe - Reset your password",
        message=(
            f"Hi {user.username}, \n\n"
            f"We received a request to reset your password. "
            f"Click the link below to set a new one:\n\n"
            f"{reset_link}\n\n"
            f"If you didn't request this, ignore this email. "
            f"Your password will remain unchanged.\n\n"
            f"This link will expire in {settings.PASSWORD_RESET_TIMEOUT // 3600} hours.\n\n"
            f"- The Vybe Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
