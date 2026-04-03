import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import CustomUserManager


# Create your models here.
class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    email = models.EmailField(
        verbose_name="email address",
        max_length=255,
        unique=True,
        db_index=True
    )

    username = models.CharField(
        verbose_name="username",
        max_length=30,
        unique=True,
        db_index=True,
        help_text="Required. 30 characters or fewer. Letters, digits, and underscores only."
    )

    phone_number = models.CharField(
        verbose_name="phone number",
        max_length=20,
        blank=True,
        null=True,
        unique=True,
    )

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    is_active = models.BooleanField(
        default=True,
    )

    is_staff = models.BooleanField(
        default=False
    )

    is_verified = models.BooleanField(
        default=False
    )

    date_joined = models.DateTimeField(default=timezone.now)

    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = ["username"]

    class Meta:
        """
        Represents a user entity in the system.

        This class is designed to encapsulate the attributes and behavior of a user in
        the application. It includes attributes like `username`, `email`, and other
        user-related details, which are used to manage and represent user data. It
        is commonly used for authentication, user profiles, and data management.
        """
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        """
        Provides a string representation of the instance, typically useful for debugging
        or displaying meaningful information about the object.

        :return: A string representation of the instance
        :rtype: str
        """
        return self.email

    def get_full_name(self):
        """
        Generates the full name of a user by concatenating the first name and last name,
        or falls back to the email address if a full name cannot be constructed.

        :return: The full name of the user, or the email address if the full name
            does not exist.
        :rtype: str
        """
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email

    def get_short_name(self):
        """
        Returns the short name of the user based on their available attributes.

        The method checks if the `first_name` attribute exists and is not empty. If it is
        present, it returns the value of `first_name`. If `first_name` is not available,
        it falls back to the `email` attribute. This ensures that the method always
        provides a valid short name for the user by defaulting to the `email` if no
        `first_name` is set.

        :return: The user's short name, prioritizing `first_name` and defaulting to `email`.
        :rtype: str
        """
        return self.first_name or self.email
