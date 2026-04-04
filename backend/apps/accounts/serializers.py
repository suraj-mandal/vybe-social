import re

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.

    The `UserSerializer` class is designed to map and validate data for the `User`
    model. This serializer is typically used for input validation and converting
    complex data types such as Django models into native Python datatypes
    (serialization) or vice versa (deserialization).
    """

    class Meta:
        """
        Summary of what the class does.

        Defines the metadata for the User model serializer. Specifies the list of fields
        to include in the serializer as well as fields that are read-only.

        :ivar model: Reference to the User model class to be serialized.
        :type model: Type[Model]
        :ivar fields: List of fields to include in the serializer output.
        :type fields: List[str]
        :ivar read_only_fields: List of fields that should only be read from and not
            modified during serialization/deserialization.
        :type read_only_fields: List[str]
        """
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone_number",
            "is_verified",
            "date_joined",
        ]

        read_only_fields = [
            "id",
            "is_verified",
            "date_joined"
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.

    This class is responsible for serializing and validating user registration
    data. It ensures that the input satisfies specific validation rules, such as
    password confirmation and username format, and handles the creation of a new
    user object.

    :ivar password: Password provided by the user. Must be at least 8 characters long
                   and is validated using a custom password validator.
    :type password: serializers.CharField

    :ivar password_confirm: Confirmation of the password. Must match the value of
                            the `password` field.
    :type password_confirm: serializers.CharField
    """
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password],
    )

    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        """
        Represents metadata for the serialization of the User model.

        This class defines the fields to be serialized for the User model, specifies
        which fields are read-only, and provides a mapping between the model and
        deserialized data for API operations.

        :ivar model: The model to be serialized.
        :type model: type
        :ivar fields: A list of fields in the model to be included in the serialization
            process. This includes identifiers, credentials, and identifying information.
        :type fields: list[str]
        :ivar read_only_fields: A subset of fields that are designated as read-only,
            ensuring they cannot be modified during deserialization.
        :type read_only_fields: list[str]
        """
        model = User
        fields = [
            "id",
            "email",
            "username",
            "password",
            "password_confirm",
        ]

        read_only_fields = ["id", ]

    def validate_username(self, value: str) -> str:
        """
        Validates the given username against a specific pattern.

        This method ensures that the provided username adheres to the required
        format, which accepts only alphanumeric characters and underscores. If the
        provided username fails the validation, an exception is raised.

        :param value: The username string to be validated.
        :type value: str
        :return: The validated username if it meets the required pattern.
        :rtype: str
        :raises serializers.ValidationError: If the username does not match the specified
            pattern of containing only letters, numbers, and underscores.
        """
        if not re.match("^[a-zA-Z0-9_]+$", value):
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, and underscores."
            )

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Validates input attributes for password confirmation. Ensures that the provided
        password and password confirmation match. If they do not match, a validation
        error is raised indicating the mismatch.

        :param attrs: A dictionary containing input attributes where the keys
                      represent field names and the values are corresponding data.
                      Must include "password" and "password_confirm" keys.
        :type attrs: dict[str, Any]

        :return: The original input attributes if validation is successful, meaning
                 the password and password confirmation match.
        :rtype: dict[str, Any]

        :raises serializers.ValidationError: If the password and password confirmation
                                              do not match.
        """
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Passwords do not match."
            })

        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        """
        Creates and returns a new User instance based on the validated data.

        This method removes the `password_confirm` field from the input data and uses
        the remaining validated data to create a new user by calling the
        `create_user` method on the `User` model.

        :param validated_data: A dictionary containing validated user data, including
            fields required for user creation. The key `password_confirm` is removed
            from this data before the user is created.
        :type validated_data: dict[str, Any]

        :return: A newly created User instance.
        :rtype: User
        """
        validated_data.pop("password_confirm")

        user = User.objects.create_user(**validated_data)

        return user


class VerifyEmailSerializer(serializers.Serializer):
    """
    Facilitates email verification by handling and validating a unique identifier
    (uid) and token received from the client.

    This serializer is used to decode the uid, validate the user associated with it,
    and verify the provided token. It ensures that only valid, non-expired tokens are
    accepted and checks whether the user's email has already been verified.

    :ivar uid: Unique identifier for the user, encoded in the verification link.
    :type uid: str
    :ivar token: Verification token generated for the user.
    :type token: str
    """
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Validates the user verification process by decoding the given UID, checking
        the provided token, and ensuring the user is not already verified.

        :param attrs: A dictionary containing the user verification data with the keys
                      "uid" and "token".
        :type attrs: dict[str, Any]
        :return: The updated attributes dictionary containing the user object.
        :rtype: dict[str, Any]
        :raises serializers.ValidationError: If the UID is invalid or expired,
                                              if the token is invalid or expired,
                                              or if the user is already verified.
        """
        # decoding the uid
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError(
                {"uid": "Invalid or expired verification link."}
            )

        # verifying the token
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Invalid or expired verification link."}
            )

        # check if the user is already verified or not
        if user.is_verified:
            raise serializers.ValidationError(
                "This email has already been verified."
            )

        attrs["user"] = user
        return attrs
