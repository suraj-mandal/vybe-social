import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import CustomUserManager


# Create your models here.
class User(AbstractBaseUser, PermissionsMixin):
    """
    Represents a user entity in the system.

    This class is designed to encapsulate the attributes and behavior of a user in
    the application. It includes attributes like `username`, `email`, and other
    user-related details, which are used to manage and represent user data. It
    is commonly used for authentication, user profiles, and data management.

    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(verbose_name="email address", max_length=255, unique=True, db_index=True)

    username = models.CharField(
        verbose_name="username",
        max_length=30,
        unique=True,
        db_index=True,
        help_text="Required. 30 characters or fewer. Letters, digits, and underscores only.",
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

    is_staff = models.BooleanField(default=False)

    is_verified = models.BooleanField(default=False)

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

    def __str__(self) -> str:
        """
        Provides a string representation of the instance, typically useful for debugging
        or displaying meaningful information about the object.

        :return: A string representation of the instance
        :rtype: str
        """
        return self.email

    def get_full_name(self) -> str:
        """
        Generates the full name of a user by concatenating the first name and last name,
        or falls back to the email address if a full name cannot be constructed.

        :return: The full name of the user, or the email address if the full name
            does not exist.
        :rtype: str
        """
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email

    def get_short_name(self) -> str:
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


# creating a social account class to handle oauth2 from providers such as google and facebook


class SocialAccount(models.Model):
    """
    Represents a social account linked to a user, which is provided by third-party
    authentication providers such as Google or Facebook.

    This class is used to manage social authentication accounts in the system by
    storing details of the user's association with a specific social provider. It
    ensures uniqueness based on the provider and user-specific information, allowing
    users to link their accounts to third-party providers.

    :ivar id: A unique identifier for the social account.
    :type id: UUID
    :ivar user: The user associated with this social account.
    :type user: User
    :ivar provider: The provider of the social account (e.g., Google, Facebook).
    :type provider: str
    :ivar provider_user_id: The unique identifier for the user as provided by the
        social authentication provider.
    :type provider_user_id: str
    :ivar created_at: The timestamp indicating when the social account was created.
    :type created_at: datetime
    """

    class Provider(models.TextChoices):
        """
        Represents a choice enumeration for different providers.

        This class is used to define a set of predefined options for provider
        identifiers, specifically `GOOGLE` and `FACEBOOK`. Each option is
        represented as a tuple containing a key and a display value.

        :ivar GOOGLE: Represents the Google provider.
        :type GOOGLE: str
        :ivar FACEBOOK: Represents the Facebook provider.
        :type FACEBOOK: str
        """

        GOOGLE = "google", "Google"
        FACEBOOK = "facebook", "Facebook"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )

    provider = models.CharField(max_length=20, choices=Provider)

    provider_user_id = models.CharField(max_length=255, help_text="The user's unique ID from the social provider.")

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        """
        Class representing metadata configuration for the social account model.

        This class defines constraints and options for the social account model,
        including unique constraints for specific fields and descriptive names for
        the model in the admin interface.

        :ivar constraints: List of unique constraints applied to the social account model.
            The constraints ensure that a combination of `provider` and
            `provider_user_id` is unique, and that a combination of `user`
            and `provider` is also unique.
        :type constraints: List[UniqueConstraint]
        :ivar verbose_name: Singular descriptive name for the social account model.
        :type verbose_name: str
        :ivar verbose_name_plural: Plural descriptive name for the social account model.
        :type verbose_name_plural: str
        """

        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                name="unique_provider_account",
            ),
            models.UniqueConstraint(
                fields=["user", "provider"],
                name="unique_user_provider",
            ),
        ]
        verbose_name = "social account"
        verbose_name_plural = "social accounts"

    def __str__(self) -> str:
        """
        Provides a string representation of the object, primarily combining the user's email
        and the provider. This method is often used for debugging and logging purposes.

        :return: A string that concatenates the `user.email` and `provider` attributes.
        :rtype: str
        """
        return f"{self.user.email} - {self.provider}"
