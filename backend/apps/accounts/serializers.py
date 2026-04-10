import re
from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from pydantic import ValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from apps.profiles.serializers import ProfileSerializer

from .models import SocialAccount, User
from .services import FacebookAuthService, GoogleAuthService, SocialAuthService
from .validators import validate_phone_number

type AttrType = dict[str, Any]


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.

    The `UserSerializer` class is designed to map and validate data for the `User`
    model. This serializer is typically used for input validation and converting
    complex data types such as Django models into native Python datatypes
    (serialization) or vice versa (deserialization).
    """

    profile = ProfileSerializer(read_only=True)

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
            "profile",
        ]

        read_only_fields = ["id", "is_verified", "date_joined"]


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

        read_only_fields = [
            "id",
        ]

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
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

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

    def validate(self, attrs: AttrType) -> AttrType:
        """
        Validates the user verification process by decoding the given UID, checking
        the provided token, and ensuring the user is not already verified.

        :param attrs: A dictionary containing the user verification data with the keys
                      "uid" and "token".
        :type attrs: AttrType
        :return: The updated attributes dictionary containing the user object.
        :rtype: AttrType
        :raises serializers.ValidationError: If the UID is invalid or expired,
                                              if the token is invalid or expired,
                                              or if the user is already verified.
        """
        # decoding the uid
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as err:
            raise serializers.ValidationError(
                {"uid": "Invalid or expired verification link."}
            ) from err

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


# serializer for resetting the password
class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Handles the serialization and validation for password reset requests.

    This class is used in scenarios where a user needs to reset their password.
    It validates the input email address and ensures it adheres to the required
    format for further processing of the password reset request.

    :ivar email: The email address of the user requesting the password reset.
    :type email: serializers.EmailField
    """

    email = serializers.EmailField()


# serializer for confirming the password
class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Handles user password reset requests.

    This serializer is responsible for validating and processing user password reset
    requests. It validates the provided user ID and token, ensures the new passwords
    match, and verifies the token's authenticity and expiration.

    :ivar uid: Base64 encoded user identifier used to locate the user in the
        password reset process.
    :type uid: str
    :ivar token: Token used for user verification during password reset.
    :type token: str
    :ivar new_password: The new password the user wishes to set. This field is write-only,
        must meet the minimum length requirement, and is validated against defined password
        constraints.
    :type new_password: str
    :ivar new_password_confirm: A confirmation of the new password to ensure the user has
        provided matching passwords. This field is write-only and must meet the minimum
        length requirement.
    :type new_password_confirm: str
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password],
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    def validate(self, attrs: AttrType) -> AttrType:
        """
        Validates the input attributes for password reset functionality.

        This method ensures that the provided passwords match, validates the user ID
        and token for resetting the password, and retrieves the associated user
        object. If any validation checks fail, appropriate errors are raised.

        :param attrs: A dictionary containing the attributes required for validation.
            Keys in the dictionary typically include ``new_password``,
            ``new_password_confirm``, ``uid``, and ``token``.
        :type attrs: AttrType

        :return: The validated attributes, updated to include the retrieved user object.
        :rtype: AttrType

        :raises serializers.ValidationError: Raised if:
            - The provided passwords do not match.
            - The ``uid`` is invalid or expired.
            - The reset token is invalid or expired.
        """
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )

        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as err:
            raise serializers.ValidationError(
                {"uid": "Invalid or expired reset link."}
            ) from err

        # verify the token
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Invalid or expired reset link."}
            )

        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """
    Handles password change functionality for a user.

    Provides validation for the old password and ensures the new password
    matches confirmation. Enables secure management of password updates.

    :ivar old_password: The user's current password. Used for validation purposes.
    :type old_password: str
    :ivar new_password: The user's new password. Must meet provided validation and
        password policy requirements.
    :type new_password: str
    :ivar new_password_confirm: Confirmation for the new password. Should match
        new_password for validation.
    :type new_password_confirm: str
    """

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password],
    )

    new_password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    def validate_old_password(self, value: str) -> str:
        """
        Validates the provided old password against the current password of the user.
        The function ensures that the input password matches the user's existing password.

        :param value: The old password provided by the user.
        :type value: str
        :return: The validated old password if it matches the user's current password.
        :rtype: str
        :raises serializers.ValidationError: If the provided password does not match the
            user's existing password.
        """
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")

        return value

    def validate(self, attrs: AttrType) -> AttrType:
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )

        return attrs


class SocialAuthSerializer(serializers.Serializer):
    """
    Serializer for handling social authentication.

    This class is used to validate and process social authentication requests. It verifies
    access tokens with specified providers and extracts user information. Supported providers
    include Google and Facebook. The class ensures that the access token is valid for the
    selected provider before allowing further processing.

    :ivar access_token: Access token for authentication with the social provider.
    :type access_token: str
    :ivar provider: The selected social authentication provider. Allowed values are
        specified in `SocialAccount.Provider`.
    :type provider: str
    """

    access_token = serializers.CharField()
    provider = serializers.ChoiceField(choices=SocialAccount.Provider)

    def validate(self, attrs: AttrType) -> AttrType:
        """
        Validates the provided data by verifying the access token with the specified provider.
        This function ensures that the access token corresponds to a valid user by communicating
        with the provider's service and validating its authenticity.

        :param attrs: The data containing the provider and access token to be validated.
        :type attrs: AttrType
        :returns: The updated data including the user information obtained from the provider.
        :rtype: AttrType
        :raises serializers.ValidationError: If the provider is unsupported or if the access token
            is invalid for the provider.
        """
        provider = attrs["provider"]
        access_token = attrs["access_token"]

        # Step 1: verify token with the provider
        provider_services = {
            SocialAccount.Provider.GOOGLE: GoogleAuthService,
            SocialAccount.Provider.FACEBOOK: FacebookAuthService,
        }

        service: SocialAuthService | None = provider_services.get(provider)

        if not service:
            raise serializers.ValidationError(
                {"provider": f"Unsupported provider: {provider}"}
            )

        try:
            user_info = service.verify_token(access_token)
        except ValueError as e:
            raise serializers.ValidationError({"access_token": str(e)}) from e

        attrs["user_info"] = user_info

        return attrs


# creating the serializers for otp
class SendOTPSerializer(serializers.Serializer):
    """
    Handles the serialization of data for sending an OTP to a user. This serializer
    validates the phone number format to ensure compliance with specific requirements.

    The class is intended to standardize and validate user input (phone number) for
    sending OTP services. It ensures the provided phone number complies with the
    expected format and length.

    :ivar phone_number: The phone number provided for OTP services. Must be between
        7 and 15 characters long and may optionally start with a '+'.
    :type phone_number: str
    """

    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value: str) -> str:
        """
        Validates a provided phone number string for correctness.

        This function ensures that the input phone number conforms to the expected
        format using the `validate_phone_number` function. If validation fails, it
        raises a `serializers.ValidationError` with the error message from the
        `ValidationError`.

        :param value: The phone number string to validate.
        :type value: str
        :return: The validated phone number string if it passes validation.
        :rtype: str
        :raises serializers.ValidationError: When the input phone number fails
            validation.
        """
        try:
            return validate_phone_number(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e)) from e


class VerifyOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying OTP with the associated phone number.

    This serializer is used to validate and process the data required for OTP
    verification. It ensures that the phone number and OTP provided adhere to
    the expected formats and constraints.

    :ivar phone_number: The phone number provided for OTP verification.
    :type phone_number: str
    :ivar otp: The one-time password provided for verification.
    :type otp: str
    """

    phone_number = serializers.CharField(max_length=20)
    otp = serializers.CharField(
        min_length=settings.OTP_LENGTH, max_length=settings.OTP_LENGTH
    )

    def validate_phone_number(self, value: str) -> str:
        """
        Validates a phone number and ensures its correctness.

        This method attempts to validate the given phone number value by using
        the `validate_phone_number` function. If the validation fails and a
        `ValidationError` is raised, it re-raises the error as a
        `serializers.ValidationError` with the error message from the original
        exception.

        :param value: The phone number string to validate.
        :type value: str
        :return: The validated phone number string.
        :rtype: str
        :raises serializers.ValidationError: If the phone number is invalid.
        """
        try:
            return validate_phone_number(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e)) from e

    def validate_otp(self, value: str) -> str:
        """
        Validates the provided OTP value to ensure it contains only numeric digits.

        :param value: The OTP string to validate.
        : return: The validated OTP string if it contains only digits.
        :raises serializers.ValidationError: If the OTP value contains non-digit characters.
        """
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")

        return value


# serializer for logout
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value: str) -> RefreshToken:
        try:
            token = RefreshToken(value)  # type: ignore[arg-type]
        except TokenError as e:
            raise serializers.ValidationError(str(e)) from e

        return token
