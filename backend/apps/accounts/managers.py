from typing import Any

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Custom manager for handling user creation and superuser creation.

    Provides methods for creating users and superusers with additional
    field handling while ensuring that required fields such as email are
    properly validated.

    :ivar model: The model class associated with this manager.
    :type model: Type[AbstractBaseUser]
    :ivar _db: The database connection to be used for saving user instances.
    :type _db: Any
    """

    def create_user(
        self,
        email: str | None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> AbstractBaseUser:
        """
        Creates and saves a new user with the given email, password, and additional fields.

        This method ensures that the email field is provided and normalized. It creates
        a user instance with the supplied attributes, sets the password securely, and
        saves the user instance to the specified database.

        :param email: The email address of the user. This must be provided and cannot
                      be None.
        :param password: The password for the user account. If not provided, it defaults
                         to None.
        :param extra_fields: Additional fields to be included when creating the user.
        :return: The newly created user instance.
        :rtype: AbstractBaseUser
        :raises ValueError: If the "email" parameter is not provided.
        """
        if not email:
            raise ValueError("The email field must be set.")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        email: str | None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> AbstractBaseUser:
        """
        Creates and returns a superuser with the given email, password, and additional
        fields. The `is_staff`, `is_superuser`, and `is_active` fields are set to True
        by default for superusers. Custom values for `is_staff` and `is_superuser`
        fields resulting in False will raise a ValueError.

        :param email: The email address associated with the superuser.
        :param password: The password for the superuser. It may be None.
        :param extra_fields: A dictionary of additional fields to set on the user.
        :return: An instance of the `AbstractBaseUser` representing the created
            superuser.
        :rtype: AbstractBaseUser
        :raises ValueError: If `is_staff` is set to False.
        :raises ValueError: If `is_superuser` is set to False.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff", False):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser", False):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
