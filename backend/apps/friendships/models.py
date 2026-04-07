import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Greatest, Least

from apps.accounts.models import User

from .managers import FriendRequestManager


class FriendRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_friend_requests")

    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_friend_requests"
    )

    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)

    message = models.TextField(
        max_length=300, blank=True, help_text="Optional message from the sender to introduce themselves."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    responded_at = models.DateTimeField(null=True, blank=True)

    objects = FriendRequestManager()

    class Meta:
        verbose_name = "friend request"
        verbose_name_plural = "friend requests"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                Least("sender", "receiver"), Greatest("sender", "receiver"), name="unique_friend_pair"
            ),
            models.CheckConstraint(
                condition=~models.Q(sender=models.F("receiver")),
                name="prevent_self_friend_request",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sender} -> {self.receiver} ({self.status})"


def are_friends(first_user: User, second_user: User) -> bool:
    """
    Determines if two users are friends.

    This function checks if the two specified users are friends by
    querying the FriendRequest object. It returns a boolean value
    indicating their friendship status.

    :param first_user: The first user being checked for friendship.
    :type first_user: User
    :param second_user: The second user being checked for friendship.
    :type second_user: User
    :return: A boolean value indicating whether the two users are friends.
    :rtype: bool
    """
    return FriendRequest.objects.are_friends(first_user, second_user)
