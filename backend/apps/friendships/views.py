from datetime import timedelta

from django.conf import settings as django_settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.friendships.models import (
    FriendRequest,
    update_friend_request_from_pending,
    update_friend_request_to_pending,
)
from apps.friendships.serializers import (
    FriendRequestSerializer,
    FriendSummarySerializer,
)


# view to send a friend request
class SendFriendRequestView(APIView):
    """
    Handles sending friend requests between users.

    This view ensures that friend requests are created or updated appropriately based on
    existing relationships or previous interactions, while adhering to internal rules like
    self-request prevention, duplicate request handling, and cooldown periods for re-requests.
    It allows authenticated users to send requests to other users along with an optional
    message payload.

    :ivar permission_classes: The list of permission classes required to access this view,
                              ensuring endpoints are restricted to authenticated users only.
    :type permission_classes: list
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, user_id: str) -> Response:
        """
        Handles the process of sending a friend request from the currently authenticated user to the
        specified user. Ensures proper validation for self-requests, duplicate requests, and cooldown
        periods for declined requests. Creates a new friend request if no prior relationship exists,
        or updates the status of an existing friend request appropriately.

        :param request: The HTTP request object, containing user data and optional message content.
        :type request: Request
        :param user_id: The unique identifier of the target user who will receive the friend request.
        :type user_id: str
        :return: A Response object containing either success data, informational messages, or error
                 messages depending on the state of the friend request.
        :rtype: Response
        """
        receiver = get_object_or_404(User, id=user_id)
        request_user: User = request.user  # type: ignore[assignment]

        if receiver == request_user:
            # sending requests to self is never allowed
            return Response(
                {"detail": "You cannot send a friend request to yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # checking for existing rows between these two users
        existing: FriendRequest = FriendRequest.objects.filter(
            Q(sender=request_user, receiver=receiver)
            | Q(sender=receiver, receiver=request_user)
        ).first()

        if existing:
            match existing.status:
                case FriendRequest.Status.ACCEPTED:
                    return Response(
                        {"detail": "You are already friends with this user."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                case FriendRequest.Status.PENDING:
                    return Response(
                        {
                            "detail": "A pending friend request already exists between you and this user."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                case FriendRequest.Status.DECLINED:
                    if existing.receiver == request_user:
                        # The current user is the one who previously declined the friend request
                        # So, they should be able to send the request again
                        message = request.data.get("message", "").strip()[:300]

                        existing = update_friend_request_to_pending(
                            existing_friend_request=existing,
                            sender=request_user,
                            receiver=receiver,
                            message=message,
                        )

                        serializer = FriendRequestSerializer(existing)
                        return Response(
                            serializer.data, status=status.HTTP_201_CREATED
                        )

                    # The current user was the sender who GOT declined,
                    # So, they should be able to send the request based on the configured
                    # cooldown period

                    receiver_cooldown: int = (
                        receiver.profile.friend_request_cooldown
                    )
                    if receiver_cooldown is not None:
                        cooldown_days = receiver_cooldown
                    else:
                        cooldown_days = getattr(
                            django_settings, "FRIEND_REQUEST_COOLDOWN_DAYS", 20
                        )

                    if cooldown_days == 0:
                        # user will not be able to send the friend request anymore
                        return Response(
                            {
                                "detail": "This user does not accept re-requests after declining."
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )

                    cooldown_end = (
                        existing.responded_at + timedelta(days=cooldown_days)
                        if existing.responded_at is not None
                        else timezone.now()
                    )

                    # check for the cooldown period now
                    if timezone.now() < cooldown_end:
                        remaining = (cooldown_end - timezone.now()).days + 1
                        return Response(
                            {
                                "detail": (
                                    f"You cannot re-send a friend request to this user yet. "
                                    f"Try again in {remaining} days(s)."
                                )
                            },
                            status=status.HTTP_429_TOO_MANY_REQUESTS,
                        )

                    # cooldown expired - updating the row back to PENDING
                    message = request.data.get("message", "").strip()[:300]

                    existing = update_friend_request_to_pending(
                        existing_friend_request=existing,
                        sender=request_user,
                        receiver=receiver,
                        message=message,
                    )

                    serializer = FriendRequestSerializer(existing)
                    return Response(
                        serializer.data,
                        status=status.HTTP_201_CREATED,
                    )

        # no existing row present, so we create a fresh request here
        message = request.data.get("message", "").strip()[:300]

        friend_request = FriendRequest.objects.create(
            sender=request_user,
            receiver=receiver,
            message=message,
        )

        serializer = FriendRequestSerializer(friend_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# view to accept a friend request
class AcceptFriendRequestView(APIView):
    """
    Handles acceptance of a friend request.

    Provides functionality to accept a pending friend request if the user is
    the intended receiver and the request has not been handled already.
    Validates and processes friend requests to ensure correct behavior and
    updates their status accordingly.

    :ivar permission_classes: Specifies the permissions required to access
        this view.
    :type permission_classes: list
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, request_id: str) -> Response:
        """
        Handles the POST request to accept a friend request. Validates that the requesting
        user is the receiver of the friend request and that the friend request is currently
        in the pending status before approving it.

        :param request: The HTTP request object containing the user and request information.
        :type request: Request
        :param request_id: The unique identifier of the friend request to be processed.
        :type request_id: str
        :return: A Response object containing the serialized friend request data upon
                 successful acceptance or an error message with the appropriate HTTP status
                 in case of validation failure.
        :rtype: Response
        """
        friend_request = get_object_or_404(FriendRequest, id=request_id)

        # Only the receiver can accept the friend request
        if friend_request.receiver != request.user:
            return Response(
                {"detail": "You can only accept requests sent to you."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # only pending friend requests can be accepted
        if friend_request.status != FriendRequest.Status.PENDING:
            return Response(
                {"detail": f"This request is already {friend_request.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        friend_request = update_friend_request_from_pending(
            existing_friend_request=friend_request,
            status=FriendRequest.Status.ACCEPTED,
        )

        serializer = FriendRequestSerializer(friend_request)
        return Response(serializer.data, status=status.HTTP_200_OK)


# view to decline a friend request
class DeclineFriendRequestView(APIView):
    """
    Handles the decline of a friend request in the system.

    This class provides an API endpoint that allows an authenticated user to
    decline a friend request if specific conditions are met. The declining process
    ensures that only the intended recipient of a friend request can decline it,
    and only requests with a pending status can be processed.

    :ivar permission_classes: Specifies the permissions required to access this
        view. Only authenticated users are allowed.
    :type permission_classes: list
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, request_id: str) -> Response:
        """
        Handles the logic for declining a friend request by the receiver. The method ensures
        proper validation of the friend request's status and enforces that only the
        designated receiver can perform this action.

        :param request: The HTTP request object containing metadata about the request.
        :type request: Request
        :param request_id: The unique identifier of the friend request to be declined.
        :type request_id: str
        :return: HTTP response containing the serialized friend request data if successful,
                 or an error message if the operation is forbidden or invalid.
        :rtype: Response
        """
        friend_request = get_object_or_404(FriendRequest, id=request_id)

        # Only the receiver can accept the friend request
        if friend_request.receiver != request.user:
            return Response(
                {"detail": "You can only decline requests sent to you."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # only pending friend requests can be declined
        if friend_request.status != FriendRequest.Status.PENDING:
            return Response(
                {"detail": f"This request is already {friend_request.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        friend_request = update_friend_request_from_pending(
            existing_friend_request=friend_request,
            status=FriendRequest.Status.DECLINED,
        )

        serializer = FriendRequestSerializer(friend_request)
        return Response(serializer.data, status=status.HTTP_200_OK)


# view to cancel a friend request
class CancelFriendRequestView(APIView):
    """
    Handles the cancellation of a friend request.

    This view allows an authenticated user to delete a pending friend request
    they previously sent. The request will be canceled only if it is still
    in a pending state, and the user attempting to cancel it is the sender
    of the request. The operation will return an appropriate HTTP response to
    indicate the success or failure of the cancellation action.

    :ivar permission_classes: Specifies the permissions required to access this view.
                              The user must be authenticated.
    :type permission_classes: list
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, request_id: str) -> Response:
        """
        Handles the deletion of a friend request. Ensures that the user can only cancel
        requests they have sent and that the request is in a pending state before
        cancellation.

        :param request: The HTTP request object containing user information.
        :type request: Request
        :param request_id: The unique identifier for the friend request to be deleted.
        :type request_id: str
        :return: An HTTP Response indicating the result of the deletion operation.
        :rtype: Response
        """
        friend_request = get_object_or_404(FriendRequest, id=request_id)

        if friend_request.sender != request.user:
            return Response(
                {"detail": "You can only cancel requests you sent."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if friend_request.status != FriendRequest.Status.PENDING:
            return Response(
                {"detail": "Only pending requests can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        friend_request.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# unfriend someone
class UnfriendView(APIView):
    """
    View for handling the unfriend functionality.

    This view allows an authenticated user to unfriend another user by sending
    a DELETE request. It verifies the existence of an accepted friend relationship
    before removing it. If the users are not friends, an appropriate error response
    is returned.

    :ivar permission_classes: List of permission classes required for this view.
    :type permission_classes: list
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, user_id: str) -> Response:
        """
        Deletes an existing friendship relationship between the logged-in user and another user. If the users are not
        currently friends, the operation will return an error.

        :param request: The HTTP request object containing the authenticated user's details.
        :type request: Request
        :param user_id: The ID of the user to unfriend.
        :type user_id: str
        :return: A HTTP response indicating the result of the operation. Returns a 204 status code if the friendship
                 is successfully deleted. Returns a 400 status code with an error message if the users are not friends.
        :rtype: Response
        """
        unfriend_user = get_object_or_404(User, id=user_id)

        # now check if they are friends or not
        existing_friend_request = FriendRequest.objects.filter(
            Q(sender=request.user, receiver=unfriend_user)
            | Q(sender=unfriend_user, receiver=request.user),
            status=FriendRequest.Status.ACCEPTED,
        ).first()

        if not existing_friend_request:
            return Response(
                {"detail": "You are not friends with this user"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # delete the relationship between the current user and the user to unfriend
        existing_friend_request.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# get the list of friends
class FriendsListView(ListAPIView):
    """
    Represents a view for retrieving a list of friends of the authenticated user.

    This class provides functionality to return the list of friends associated with
    the currently authenticated user. It leverages Django REST framework's
    ListAPIView to structure the API response and ensures that the user is
    authenticated before accessing the data.

    :ivar permission_classes: Defines the permissions required to access this view.
    :type permission_classes: list[IsAuthenticated]
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FriendSummarySerializer

    # implements pagination by default
    def get_queryset(self):
        """
        Retrieves and returns the queryset representing friends of the current user. This is a
        filtering operation tailored to fetch only those FriendRequest objects that denote
        friendship associations of the authenticated user.

        :return: A queryset of FriendRequest objects representing the user's friends
        :rtype: QuerySet
        """
        return FriendRequest.objects.friends_of(self.request.user)


# get the list of pending received requests
class PendingReceivedRequestsView(ListAPIView):
    """
    Handles the listing of pending friend requests received by the authenticated user.

    This view provides a GET functionality to retrieve all pending friend requests
    received by the user. It ensures that the user making the request is authenticated,
    and utilizes a serializer to process the pending friend requests data.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer

    # implements pagination here by default
    def get_queryset(self):
        """
        Returns the queryset of pending friend requests received by the
        currently authenticated user.

        :return: A queryset containing `FriendRequest` objects filtered by
            pending requests received by the current user.
        :rtype: QuerySet
        """
        return FriendRequest.objects.pending_received(self.request.user)


# get the list of pending ent requests
class PendingSentRequestsView(ListAPIView):
    """
    Handles the retrieval of pending friend requests sent by the authenticated user.

    This view is responsible for fetching a list of friend requests that the authenticated
    user has sent but are still pending (not yet accepted or rejected). It uses serialization
    to provide the data in a structured format suitable for API responses.

    :ivar permission_classes: Specifies the list of permissions required to access this view.
    :type permission_classes: list[permissions.BasePermission]
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer

    # implements pagination here by default
    def get_queryset(self):
        """
        Retrieves the queryset of pending friend requests sent by the current user.

        This method is designed to return a QuerySet containing all friend requests
        that are in a pending state and were sent by the user making the current
        request. It utilizes the `pending_sent` method of the `FriendRequest.objects`
        manager to filter the data specific to the requesting user.

        :return: A QuerySet of pending friend requests sent by the current user.
        :rtype: QuerySet
        """
        return FriendRequest.objects.pending_sent(self.request.user)
