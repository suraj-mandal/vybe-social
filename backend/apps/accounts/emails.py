from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


def send_verification_email(user: User) -> None:
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
