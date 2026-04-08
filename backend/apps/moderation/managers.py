from django.db.models import Manager, Q

from apps.accounts.models import User


class BlockManager(Manager):
    """
    Manages the blocking relationships among users.

    Provides methods to query and manage blocked or blocking users. This class
    extends the functionalities of the `Manager` class and is typically used
    to handle user relationships in applications where blocking functionality
    is required.
    """

    def is_blocked(self, blocker: User, blocked: User) -> bool:
        """
        Determine if a given user is blocked by another user.

        This method checks whether the specified user (`blocked`) is blocked by the
        user (`blocker`) in the context of the system. It searches for an existing
        blocking relationship in the dataset and returns a boolean value indicating
        whether such a relationship exists.

        :param blocker: The user who might have applied the block.
        :type blocker: User
        :param blocked: The user who might be blocked by the blocker.
        :type blocked: User
        :return: True if the blocked user is currently blocked by the blocker, False otherwise.
        :rtype: bool
        """
        return self.filter(blocker=blocker, blocked=blocked).exists()

    def is_either_blocked(self, first_user: User, second_user: User) -> bool:
        """
        Determines if there is a blocking relationship between two users. This method checks if
        either `first_user` has blocked `second_user` or if `second_user` has blocked `first_user`.

        :param first_user: The user object representing the first user.
        :type first_user: User
        :param second_user: The user object representing the second user.
        :type second_user: User
        :return: A boolean value indicating whether a blocking relationship exists between
                 the two users.
        :rtype: bool
        """
        return self.filter(
            Q(blocker=first_user, blocked=second_user) | Q(blocker=second_user, blocked=first_user)
        ).exists()

    def blocked_user_ids(self, user: User) -> set[str]:
        """
        Retrieves a set of user IDs that have been blocked by a specified user.

        :param user: The user for whom to retrieve the blocked user IDs.
        :type user: User
        :return: A set containing the IDs of users who have been blocked by the
                 specified user.
        :rtype: Set[str]
        """
        return set(self.filter(blocker=user).values_list("blocked_id", flat=True))

    def blocked_by_user_ids(self, user: User) -> set[str]:
        """
        Retrieve a set of user IDs that have blocked a given user.

        This method evaluates the relationship between users based on a filtering
        criterion where the provided user is in the "blocked" field. It returns a set
        of IDs, representing all users who have blocked the specified user.

        :param user: The `User` instance representing the user who is blocked by others.
        :type user: User
        :return: A set of user IDs (`str`) that belong to users who have blocked the
            given user.
        :rtype: Set[str]
        """
        return set(self.filter(blocked=user).values_list("blocker_id", flat=True))


class MuteManager(Manager):
    """
    Provides functionality for managing and retrieving user mute relationships.

    This manager class is responsible for handling operations related to muting
    and retrieving muted user data. It supports determining whether a user has
    muted another user and retrieving sets of muted user IDs for a given user.
    """

    def is_muted(self, muter: User, muted: User) -> bool:
        """
        Determines whether a specific user has muted another user.

        This method checks if there is a record in the system indicating that
        the `muter` user has muted the `muted` user. It returns a boolean value
        indicating the presence or absence of such a record.

        :param muter: The user who may have muted the other user.
        :type muter: User
        :param muted: The user who may have been muted by the `muter`.
        :type muted: User
        :return: A boolean value indicating whether the `muter` has muted the `muted`.
        :rtype: bool
        """
        return self.filter(muter=muter, muted=muted).exists()

    def muted_user_ids(self, user: User) -> set[str]:
        """
        Fetch the set of user IDs that have been muted by the given user.

        :param user: The user for whom the muted user IDs are being retrieved.
        :type user: User
        :return: A set containing the IDs of users muted by the given user.
        :rtype: Set[str]
        """
        return set(self.filter(muter=user).values_list("muted_id", flat=True))
