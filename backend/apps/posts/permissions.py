from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User


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
        request_user: User = request.user  # type: ignore[assignment]
        return obj.author_id == request_user.id
