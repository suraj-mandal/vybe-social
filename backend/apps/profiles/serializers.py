from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializes and deserializes `Profile` model instances to and from JSON.

    The `ProfileSerializer` is responsible for defining the structure and rules
    for converting `Profile` model instances into JSON representations, and vice
    versa. It also includes functionality for read-only fields such as `id`,
    `username`, and timestamps for creation and update. This serializer is mainly
    used for API interactions.

    :ivar username: The username retrieved from the related `User` model,
        displayed as read-only and sourced from `user.username`.
    :type username: str
    """

    # get the username from the related User - read-only, for display
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        """
        Defines metadata for the Profile model and specifies field configurations.

        This class serves as a Django serializer `Meta` class configuration for the Profile
        model. It lists the fields that should be included in the serialization and defines
        which of those fields are read-only.

        :ivar model: The model associated with this serializer configuration.
        :type model: type
        :ivar fields: List of fields to be included in the serializer.
        :type fields: list[str]
        :ivar read_only_fields: List of fields that are read-only in the serializer.
        :type read_only_fields: list[str]
        """

        model = Profile
        fields = [
            "id",
            "username",
            "bio",
            "avatar_url",
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
