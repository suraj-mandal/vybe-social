from rest_framework import serializers

from apps.media.models import Media
from apps.media.s3_service import generate_presigned_read_url

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for managing and formatting user profile data.

    This serializer is designed to serialize and deserialize `Profile` model
    instances, including fields for retrieving user-related data, such as
    username and avatar URLs. It supports both read and write operations for
    specific fields while maintaining read-only constraints for certain system-
    generated or user-identity attributes.

    :ivar username: Retrieves the username of the associated user. This field is
        read-only and used for display purposes.
    :type username: str

    :ivar avatar_url: Generates and provides a pre-signed URL for accessing the
        user's avatar image. This is a read-only computed field.
    :type avatar_url: str
    """

    # get the username from the related User - read-only, for display
    username = serializers.CharField(source="user.username", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        """
        Meta class for configuring the `Profile` serializer.

        This class defines the fields to include in the serialized representation
        and specifies fields that are read-only. It is tailored to ensure proper
        interaction between the `Profile` model and external systems, such as
        RESTful APIs.

        :ivar model: The model associated with this serializer.
        :type model: Profile

        :ivar fields: The list of fields to include in the serialization process.
            Includes both read and write capabilities for respective fields.
            - "id", "username", and "created_at" are examples of read-only fields.
            - "avatar" accepts media UUID for writing, while "avatar_url" provides
              a presigned URL for reading.
        :type fields: list

        :ivar read_only_fields: The subset of `fields` that are strictly read-only.
            These fields cannot be modified through the serializer, ensuring data integrity
            for attributes such as identity-related or system-generated values.
        :type read_only_fields: list
        """

        model = Profile
        fields = [
            "id",
            "username",
            "bio",
            "gender",
            "avatar",  # write - accepts media UUID
            "avatar_url",  # read - returns presigned URL
            "location",
            "website",
            "date_of_birth",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "username",
            "created_at",
            "updated_at",
        ]

    def get_avatar_url(self, profile: Profile) -> str | None:
        """
        Retrieve the avatar URL for a given user profile.

        This function generates a pre-signed URL for accessing the avatar image
        associated with the provided profile. If the profile does not have an
        avatar, the function returns None.

        :param profile: The user profile containing the avatar to retrieve.
        :type profile: Profile
        :return: A pre-signed URL for the avatar image, or None if no avatar
                 is set for the profile.
        :rtype: Optional[str]
        """
        profile_avatar: Media = profile.avatar

        if not profile_avatar:
            return None

        return generate_presigned_read_url(profile_avatar.s3_key)
