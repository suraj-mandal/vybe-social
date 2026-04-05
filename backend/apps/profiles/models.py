import uuid

from django.conf import settings
from django.db import models

# Create your models here.


class Profile(models.Model):
    """
    Represents a user profile within the application.

    This class is used to store additional information and metadata
    associated with a user account. It is linked to the main user model
    via a one-to-one relationship. Instances of this class are created
    and updated to maintain user-specific details beyond the default
    user model fields.

    :ivar id: Unique identifier for the profile. Automatically generated
              as a UUID.
    :ivar user: The user associated with this profile. This is a one-to-one
                relationship with the main user model.
    :ivar bio: A short biography or description for the user. Maximum
               length is 500 characters. This field is optional.
    :ivar avatar_url: URL pointing to the user's avatar image. Typically,
                      an S3 presigned URL is generated for this field.
                      Maximum length is 500 characters. This field is optional.
    :ivar location: The user's location or address as a string. Maximum
                    length is 100 characters. This field is optional.
    :ivar website: User's personal or professional website URL. Maximum
                   length is 200 characters. This field is optional.
    :ivar date_of_birth: The user's date of birth. This field is optional.
    :ivar created_at: Timestamp for when the profile was created. Automatically
                      generated when the profile is first created.
    :ivar updated_at: Timestamp for the last update to the profile. Automatically
                      updated whenever the profile is modified.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    bio = models.TextField(max_length=500, blank=True)

    avatar_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="S3 presigned URL will be generated from the S3 key.",
    )

    location = models.CharField(max_length=100, blank=True)

    website = models.URLField(max_length=200, blank=True)

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
