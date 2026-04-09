from rest_framework import serializers

from apps.moderation.models import Block, Mute


class BlockedUserSerializer(serializers.ModelSerializer):
    """
    Serializer class for handling blocked user data.

    This class is used to serialize and manage data related to blocked users. It includes a
    custom method to retrieve details of a blocked user and ensures that the serialized data
    includes specific fields while adhering to the defined model structure.

    """

    blocked_user = serializers.SerializerMethodField()

    class Meta:
        model = Block
        fields = [
            "id",
            "blocked_user",
            "created_at",
        ]
        read_only_fields = fields

    def get_blocked_user(self, current_blocked: Block) -> dict[str, str]:
        """
        Retrieve details of a blocked user.

        This method takes a blocked user object and extracts relevant information such as the
        user's ID, username, and full name. It organizes these details into a dictionary
        format for convenient access.

        :param current_blocked: The blocked user object encapsulating details about the
            blocked user.
        :type current_blocked: Block
        :return: A dictionary containing the blocked user's ID, username, and full name.
        :rtype: dict[str, str]
        """
        return {
            "id": str(current_blocked.blocked.id),
            "username": current_blocked.blocked.username,
            "full_name": current_blocked.blocked.get_full_name(),
        }


class MutedUserSerializer(serializers.ModelSerializer):
    """
    Serializer for muted user objects.

    This class provides functionality to serialize muted user information by extending
    `serializers.ModelSerializer`. It includes fields for the muted user's details and other
    relevant metadata. The `muted_user` field is populated using a custom method.
    """

    muted_user = serializers.SerializerMethodField()

    class Meta:
        model = Mute
        fields = [
            "id",
            "muted_user",
            "created_at",
        ]
        read_only_fields = fields

    def get_muted_user(self, current_muted: Mute) -> dict[str, str]:
        """
        Retrieve information about a muted user.

        This function extracts the ID, username, and full name of a muted user from a
        provided Mute object and returns it in the form of a dictionary.

        :param current_muted: The Mute object containing information about the muted user.
        :type current_muted: Mute
        :return: A dictionary containing the muted user's ID, username, and full name.
        :rtype: dict[str, str]
        """
        return {
            "id": str(current_muted.muted.id),
            "username": current_muted.muted.username,
            "full_name": current_muted.muted.get_full_name(),
        }
