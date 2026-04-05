from rest_framework.permissions import BasePermission


class IsVerified(BasePermission):
    message = "You must verify your email before performing this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "is_verified")
            and request.user.is_verified
        )
