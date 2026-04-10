# Create your views here.
from collections.abc import Iterable

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.moderation.models import Block, Mute
from apps.moderation.serializers import (
    BlockedUserSerializer,
    MutedUserSerializer,
)


class BlockUserView(APIView):
    """
    POST /api/blocks/<uuid:user_id>/

    View that handles user blocking functionality.

    This class-based view provides the ability for an authenticated user to block
    another user. Blocking prevents interactions between the blocker and the blocked
    user, such as sending friend requests. Any existing friend requests between
    the two users are also deleted when a block occurs.

    User should be authenticated to handle this.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, user_id: str) -> Response:
        """
        Handles the blocking functionality of a user in a social networking application.
        This operation ensures that a user cannot block themselves and prevents duplicate
        blocking of the same user. It also cleans up by deleting any existing friend requests
        between the blocker and the blocked user.

        :param request: The HTTP request object containing metadata about the request including
            the auth user as `request.user`.
        :type request: Request
        :param user_id: The unique identifier of the user to be blocked.
        :type user_id: str
        :return: The HTTP response indicating the success or failure of the blocking operation.
        :rtype: Response
        """
        blocked_user = get_object_or_404(User, id=user_id)
        blocker: User = request.user  # type: ignore[assignment]

        if blocked_user == blocker:
            # self-blocking is not allowed
            return Response(
                {
                    "detail": "You cannot block yourself.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check if already blocked
        if Block.objects.is_blocked(blocker, blocked_user):
            return Response(
                {"detail": "You have already blocked this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # now do the actual blocking
        with transaction.atomic():
            Block.objects.create(blocker=blocker, blocked=blocked_user)

            # delete any existing friend request that was present before
            FriendRequest.objects.filter(
                Q(sender=blocker, receiver=blocked_user)
                | Q(sender=blocked_user, receiver=blocker)
            ).delete()

            return Response(
                {"detail": f"You have blocked {blocked_user.username}"},
                status=status.HTTP_201_CREATED,
            )


class UnblockUserView(APIView):
    """
    DELETE /api/blocks/<uuid:user_id>/

    Provides the functionality to unblock a user.

    This view handles the removal of a blocking relationship between the
    authenticated user and a specified user. It ensures the user to be
    unblocked exists and that such a blocking relationship currently exists
    before performing the unblock operation.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, user_id: str):
        """
        Deletes a block relationship between the requesting user and another user
        specified by the ``user_id`` provided. If no block relationship exists,
        an appropriate error response is returned. On successful deletion, a no-content
        response is provided to indicate the block was removed.

        :param request: The HTTP request containing the authenticated user making the delete request.
        :type request: Request
        :param user_id: The unique identifier of the user whose block relationship
                        is to be deleted.
        :type user_id: str
        :return: A response object with status indicating success or failure of the operation.
        :rtype: Response
        """
        blocked_user = get_object_or_404(User, id=user_id)

        block: Block | None = Block.objects.filter(
            blocker=request.user, blocked=blocked_user
        ).first()

        if not block:
            # the user is not blocked at all
            return Response(
                {"detail": "You have not blocked this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        block.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockedUsersListView(ListAPIView):
    """
    GET /api/blocks/
    Represent a view for retrieving a list of blocked users.

    This class provides functionality to fetch and serialize information about
    users blocked by the currently authenticated user. It requires the user to
    be authenticated and uses a specific serializer to return the data.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BlockedUserSerializer

    def get_queryset(self) -> Iterable[BlockedUserSerializer]:
        """
        Retrieves a queryset of blocked users for the current requesting user.

        This method returns a set of `BlockedUserSerializer` instances that
        represent all users blocked by the currently authenticated user. The
        queryset is optimized using `select_related` to prefetch the `blocked`
        relationship, improving database access performance.

        :returns: A set of blocked user serializers representing the users blocked
                  by the requesting user.
        :rtype: set[BlockedUserSerializer]
        """
        return Block.objects.filter(blocker=self.request.user).select_related(
            "blocked"
        )


class MuteUserView(APIView):
    """
    POST /api/mutes/<uuid:user_id>/

    Handles muting of a user by the authenticated user.

    This view allows an authenticated user to mute another user. It ensures that
    a user cannot mute themselves or mute the same user multiple times. Upon
    success, it records the mute relationship between the muter and the muted
    user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, user_id: str) -> Response:
        """
        Handles the muting of a user identified by their user ID. The method ensures that a user cannot mute themselves,
        prevents duplicate mute actions, and creates a mute record when valid conditions are met. Returns a JSON response
        indicating the status of the operation.

        :param request: The HTTP request object containing the user initiating the mute action.
        :type request: Request
        :param user_id: The unique identifier of the user to be muted.
        :type user_id: str
        :return: An HTTP response with a success message upon successful muting or an error message otherwise.
        :rtype: Response
        """
        muted_user: User = get_object_or_404(User, id=user_id)
        muter: User = request.user  # type: ignore[assignment]

        if muted_user == muter:
            return Response(
                {"detail": "You cannot mute yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Mute.objects.is_muted(muter, muted_user):
            return Response(
                {"detail": "You have already muted this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Mute.objects.create(muter=muter, muted=muted_user)

        return Response(
            {"detail": f"You have muted {muted_user.username}"},
            status=status.HTTP_201_CREATED,
        )


class UnmuteUserView(APIView):
    """
    DELETE /api/mutes/<uuid:user_id>/unmute/

    Provides functionality to unmute a previously muted user.

    This view handles the deletion of a mute relationship between the current user
    and the specified user, allowing the current user to unmute another user. It
    requires the user to be authenticated and ensures that a mute relationship
    exists before removing it.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, user_id: str) -> Response:
        """
        Handles the deletion of a mute relationship between the current user and a specified user.

        The method checks if the current user has muted the target user. If the mute relationship
        exists, it deletes the relationship, effectively unmuting the target user. If the mute
        relationship does not exist, a response indicating this is returned.

        :param request: The HTTP request object containing details about the current request.
        :type request: Request
        :param user_id: The unique identifier of the user to unmute.
        :type user_id: str
        :return: A response indicating the result of the unmute operation. Returns a 204 No Content
                 status if the unmute is successful, or a 400 Bad Request status if no mute relationship
                 exists.
        :rtype: Response
        """
        user_to_unmute: User = get_object_or_404(User, id=user_id)
        current_user: User = request.user  # type: ignore[assignment]

        mute: Mute | None = Mute.objects.filter(
            muter=current_user, muted=user_to_unmute
        ).first()

        if not mute:
            return Response(
                {"detail": "You have not muted this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mute.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MutedUsersListView(ListAPIView):
    """
    GET /api/mutes/

    Handles the listing of muted users for the authenticated user.

    This class-based view retrieves and displays the list of users muted by the
    currently authenticated user. It enforces authentication and uses serialization
    to format the data appropriately.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MutedUserSerializer

    def get_queryset(self) -> Iterable[MutedUserSerializer]:
        """
        Fetches the list of users muted by the currently authenticated user.

        This method retrieves queryset objects representing users muted by the currently
        authenticated user. It performs database filtering based on the `muter` field, which
        is set to the currently requesting user. The muted users are fetched with their
        related data for performance optimization using `select_related`.

        :return: Queryset of muted users serialized with `MutedUserSerializer`
        :rtype: Iterable[MutedUserSerializer]
        """
        return Mute.objects.filter(muter=self.request.user).select_related(
            "muted"
        )
