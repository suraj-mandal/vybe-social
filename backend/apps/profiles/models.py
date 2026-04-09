import uuid

from django.conf import settings
from django.db import models

# Create your models here.


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    bio = models.TextField(max_length=500, blank=True)

    avatar = models.ForeignKey(
        "media.Media",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    location = models.CharField(max_length=100, blank=True)

    website = models.URLField(max_length=200, blank=True)

    friend_request_cooldown = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Days before a declined sender can re-send a friend request. "
            "Null - use system default. 0 = permanent (never allow re-requests)."
        ),
    )

    date_of_birth = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Represents a user profile in the system.

        This class is used to manage user-related information such as details,
        settings, or metadata for the user profiles, and it provides an interface
        for interacting with such data.
        """

        verbose_name = "profile"
        verbose_name_plural = "profiles"

    def __str__(self):
        return f"Profile of {self.user.username}"
