import uuid

from django.conf import settings
from django.db import models

from apps.moderation.managers import BlockManager, MuteManager, User

# Create your models here.


class Block(models.Model):
    """
    Represents a block relationship between two users.

    The Block model is used for managing block relationships, where a user can block
    another user within the system. It includes metadata to ensure valid blocking
    behavior and prevent self-blocking. Instances of this model capture who initiated
    the block, who is blocked, and the timestamp when the block occurred.

    Introduces a directional block, which means two users can block each other separately.

    :ivar id: Unique identifier for the block instance.
    :type id: UUID
    :ivar blocker: Reference to the user initiating the block.
    :type blocker: ForeignKey
    :ivar blocked: Reference to the user being blocked.
    :type blocked: ForeignKey
    :ivar created_at: Timestamp of when the block was created.
    :type created_at: DateTime
    """

    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_given",
    )

    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_received",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    objects = BlockManager()

    class Meta:
        verbose_name = "block"
        verbose_name_plural = "blocks"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_block",
            ),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="prevent_self_block",
            ),
        ]

    def __str__(self) -> str:
        """
        Provides a string representation of the object that describes the relationship
        between the `blocker` and the `blocked` attributes.

        :return: A string in the format "{blocker} blocked {blocked}".
        :rtype: str
        """
        return f"{self.blocker} blocked {self.blocked}"


class Mute(models.Model):
    """
    Represents a model for managing user mute actions.

    This class defines a database model used to track mute relationships
    between users. It provides the ability for a user to mute another user
    while ensuring vital constraints such as preventing a user from muting
    themselves and ensuring uniqueness of each mute relationship.

    :ivar id: The unique identifier for the mute instance.
    :type id: UUID
    :ivar muter: The user who performs the mute action.
    :type muter: ForeignKey
    :ivar muted: The user being muted.
    :type muted: ForeignKey
    :ivar created_at: The timestamp when the mute was created.
    :type created_at: DateTime
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    muter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mutes_given",
    )

    muted = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mutes_received",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    objects = MuteManager()

    class Meta:
        verbose_name = "mute"
        verbose_name_plural = "mutes"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["muter", "muted"],
                name="unique_mute",
            ),
            models.CheckConstraint(
                condition=~models.Q(muter=models.F("muted")),
                name="prevent_self_mute",
            ),
        ]

    def __str__(self) -> str:
        """
        Provides a string representation of the object.

        :return: A string describing the "muter" and "muted" attributes of the object.
        :rtype: str
        """
        return f"{self.muter} muted {self.muted}"


def is_blocked(blocker: User, blocked: User) -> bool:
    """
    Determine if a user is blocked by another user.

    This function checks if the specified `blocked` user is blocked
    by the `blocker` user by querying the Block database model.

    :param blocker: The user who might have blocked the other user.
    :type blocker: User
    :param blocked: The user who might be blocked.
    :type blocked: User
    :return: True if the `blocked` user is blocked by the `blocker` user,
        otherwise False.
    :rtype: bool
    """
    return Block.objects.is_blocked(blocker, blocked)


def is_either_blocked(first_user: User, second_user: User) -> bool:
    """
    Check if either of the two users has blocked the other.

    This function checks whether there is a blocking relationship between the
    two users provided. It uses the `Block` model to determine if there is
    a block initiated by one user against the other.

    :param first_user: The first user to be checked in the blocking relationship.
    :type first_user: User
    :param second_user: The second user to be checked in the blocking relationship.
    :type second_user: User
    :return: True if one of the users has blocked the other; otherwise, False.
    :rtype: bool
    """
    return Block.objects.is_either_blocked(first_user, second_user)


def is_muted(muter: User, muted: User) -> bool:
    """
    Determine if one user has muted another user.

    This function checks whether the given `muter` user has muted the
    specified `muted` user by querying the database for a mute record.

    :param muter: The user who may have muted the other user.
    :type muter: User
    :param muted: The user who may be muted by the muter.
    :type muted: User
    :return: A boolean value indicating whether the muter has muted the muted user.
    :rtype: bool
    """
    return Mute.objects.is_muted(muter, muted)
