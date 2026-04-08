from rest_framework import serializers

from apps.accounts.models import User
from apps.friendships.models import FriendRequest


class FriendRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for FriendRequest model.

    This serializer is used to transform FriendRequest instances into JSON-compliant
    representations. It also provides methods to retrieve sender and receiver details
    in a summarized format, including their ID, username, and full name.

    :ivar sender: Serializer field to obtain detailed sender information.
    :type sender: serializers.SerializerMethodField
    :ivar receiver: Serializer field to obtain detailed receiver information.
    :type receiver: serializers.SerializerMethodField
    """

    sender = serializers.SerializerMethodField()
    receiver = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = [
            "id",
            "sender",
            "receiver",
            "message",
            "status",
            "created_at",
            "responded_at",
        ]
        read_only_fields = fields

    def _user_summary(self, user: User):
        """
        Create a summary dictionary for the given user.

        This method extracts specific details from the user object to construct a
        dictionary containing a brief summary of the user. Only the `id`,
        `username`, and `full_name` attributes are included in the generated
        dictionary.

        :param user: The user object to extract information from.
        :type user: User

        :return: A dictionary containing the user's `id`, `username`, and
            `full_name`.
        :rtype: dict
        """
        return {"id": str(user.id), "username": user.username, "full_name": user.get_full_name()}

    def get_sender(self, friend_request: FriendRequest) -> dict[str, str]:
        """
        Retrieves a summary of the sender of a given friend request.

        Provides essential information about the sender of the friend request
        by generating a summary. This summary is represented as a dictionary
        containing key details about the sender.

        :param friend_request: The friend request object for which the sender's
            summary is to be retrieved.
        :type friend_request: FriendRequest

        :return: A dictionary containing the sender's summary, including key
            information.
        :rtype: dict[str, str]
        """
        return self._user_summary(friend_request.sender)

    def get_receiver(self, friend_request: FriendRequest) -> dict[str, str]:
        """
        Retrieve the receiver's summary from a friend request.

        The method extracts the receiver's summary details from the provided
        friend request and formats it for output.

        :param friend_request: A `FriendRequest` object representing the friend
                               request containing the receiver's details.
        :type friend_request: FriendRequest

        :return: A dictionary containing the receiver's summary information.
        :rtype: dict[str, str]
        """
        return self._user_summary(friend_request.receiver)


class FriendSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
        ]
        read_only_fields = fields

    def get_full_name(self, user: User) -> str:
        """
        Retrieve the full name of a user.

        This method retrieves the full name of a given user by invoking the
        `get_full_name` method on the provided `User` instance.

        :param user: The user object from which the full name will be retrieved.
        :type user: User
        :return: The full name of the user.
        :rtype: str
        """
        return user.get_full_name()
