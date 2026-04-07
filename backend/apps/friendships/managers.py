from collections.abc import Iterable

from django.db import models
from django.db.models import Q

from apps.accounts.models import User


class FriendRequestManager(models.Manager):
    def friends_of(self, user: User) -> Iterable[User]:
        """
        Returns a list of users who are friends of the specified user by checking
        accepted friend requests. The function identifies all requests where the
        specified user is either the sender or the receiver and the request status
        is marked as 'accepted'. It then extracts the associated friend users and
        queries their information.

        :param user: An instance of the User model representing the user whose
            friends are to be retrieved.
        :type user: User
        :return: An iterable of User instances representing friends of the
            specified user.
        :rtype: Iterable[User]
        """
        accepted_requests = self.filter(
            Q(sender=user) | Q(receiver=user),
            status="accepted",
        )

        friend_ids = set()

        for req in accepted_requests.select_related("sender", "receiver"):
            if req.sender_id == user.id:
                friend_ids.add(req.receiver_id)
            else:
                friend_ids.add(req.sender_id)

        return User.objects.filter(id__in=friend_ids)

    def are_friends(self, first_user: User, second_user: User) -> bool:
        """
        Checks if two users are friends based on their friendship status.

        :param first_user: The first user to check friendship status for.
        :type first_user: User
        :param second_user: The second user to check friendship status for.
        :type second_user: User
        :return: Returns True if the two users are friends, i.e., there exists an accepted
            friendship between them. Otherwise, returns False.
        :rtype: bool
        """
        return self.filter(
            Q(sender=first_user, receiver=second_user) | Q(sender=second_user, receiver=first_user),
            status="accepted",
        ).exists()

    def pending_received(self, user: User):
        """
        Filters the queryset to retrieve pending requests received by a specified user.

        This method filters the queryset to return only the requests where the specified
        user is the receiver and the status of the request is "pending". It uses
        `select_related` to optimize database queries when accessing related objects for
        the sender and the sender's profile.

        :param user: The user object representing the receiver of the pending requests.
        :type user: User
        :return: A queryset containing pending requests for the specified user.
        :rtype: QuerySet
        """
        return self.filter(
            receiver=user,
            status="pending",
        ).select_related("sender", "sender__profile")

    def pending_sent(self, user: User):
        """
        Returns a queryset of pending friendship requests sent by the given user.

        Filters the objects by the sender and the status of the request. The query
        selects related receiver data, including the receiver's profile, for
        optimization when accessing related objects.

        :param user: The user who has sent the friendship requests.
        :type user: User
        :return: A queryset of pending friendship requests sent by the specified user.
        :rtype: QuerySet
        """
        return self.filter(
            sender=user,
            status="pending",
        ).select_related("receiver", "receiver__profile")
