from rest_framework import permissions
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.posts.models import Post


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Permission class that grants read-only access to all users and
    write access only to the author of the object.

    This class is typically used to define object-level permissions in applications. It checks whether the user is
    authenticated and either allows read-only access to safe methods or write access if the user is the author of the
    object.

    :ivar SAFE_METHODS: A set of HTTP methods that are considered safe (e.g., GET, HEAD, OPTIONS).
    :type SAFE_METHODS: set
    """

    def has_permission(self, request, view) -> bool:
        """
        Determines whether the user making the request has the appropriate permission.

        This method evaluates if the `request` object contains a valid user who is
        authenticated. It returns a boolean value indicating whether the user meets
        these criteria.

        :param request: The HTTP request object, which represents the request
            made by the user. Expected to contain an attribute `user` that
            determines the authentication status.
        :type request: HttpRequest
        :param view: The view for which the permission is being checked.
        :type view: Any
        :return: A boolean value indicating whether the user is authenticated
            and has permission.
        :rtype: bool
        """
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(
        self, request: Request, view: APIView | None, obj
    ) -> bool:
        """
        Determine if a user has permission to access a specific object. The permission is granted
        if the HTTP method is a safe method (e.g., GET, HEAD, OPTIONS). For other methods, the
        permission is granted only if the requesting user is the author of the object.

        :param request: The HTTP request object.
        :type request: Request
        :param view: The view that is being accessed.
        :param obj: The model instance being accessed.
        :return: A boolean value indicating whether the user has the necessary permissions.
        :rtype: bool
        """
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, "author", None) or getattr(obj, "user", None)
        request_user: User = request.user  # type: ignore[assignment]
        return owner == request_user


class CanCommentOnPost(BasePermission):
    """
    Determines if a user has permission to comment on a specific post.

    This class extends BasePermission and provides custom permissions
    to determine whether a given user can comment on a post based on
    the post's visibility and their relationship with the post's author.
    It defines logic for both general permission checks and object-specific
    permission checks.

    :ivar message: The default message returned when the permission is denied.
    :type message: str
    """

    message = "You can't comment on this post."

    def has_permission(self, request: Request, view) -> bool:
        """
        Checks if the user associated with the request has the necessary permission
        to access a given view. This method ensures that the user is authenticated
        before granting permission.

        :param request: The HTTP request containing user authentication information.
        :type request: Request
        :param view: The view against which permission is being checked.
        :return: True if the user is authenticated and has permission, False otherwise.
        :rtype: bool
        """
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj: Post) -> bool:
        """
        Determines if the user has permission to interact with the object based on its visibility rules.

        :param request: The HTTP request object containing metadata about the current user and request context.
        :type request: HttpRequest
        :param view: The view instance that is associated with the request.
        :type view: Any
        :param obj: The object (Post) whose permissions need to be evaluated.
        :type obj: Post
        :return: A boolean value indicating whether the user has the permission to interact with the object.
        :rtype: bool
        """
        match obj.visibility:
            case Post.Visibility.PUBLIC:
                return True  # anyone can comment
            case Post.Visibility.PRIVATE:
                return False  # no one can comment
            case Post.Visibility.FRIENDS:
                request_user: User = request.user  # type: ignore[assignment]
                # if the author is the one commenting on their post, and
                # it is possible to comment
                # because by default, the author is not a friend of themselves.
                # so this condition needs to be added.
                return (
                    request_user == obj.author
                    or FriendRequest.objects.are_friends(
                        request_user, obj.author
                    )
                )
            case _:
                return False
