from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser
from django.db.migrations import serializer
from django.db.models import Model
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .emails import send_verification_email, send_password_reset_email
from .models import User
from .serializers import UserSerializer, RegisterSerializer, VerifyEmailSerializer, PasswordResetRequestSerializer, \
    PasswordResetConfirmSerializer, ChangePasswordSerializer


# Create your views here.

class UserListView(generics.ListAPIView):
    """
    Handles listing of User objects in the API.

    This class-based view is designed to provide a list of existing User objects.
    It uses Django REST Framework's ``ListAPIView`` to efficiently process
    and return paginated user data. The view ensures that only authenticated
    users can access this endpoint.

    :ivar queryset: The queryset defining the list of User objects to retrieve.
    :type queryset: QuerySet
    :ivar serializer_class: The serializer class used to transform User objects
        into a JSON representation.
    :type serializer_class: Serializer
    :ivar permission_classes: The list of permissions required to access this view.
    :type permission_classes: list
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class UserDetailView(generics.RetrieveAPIView):
    """
    Represents a view for retrieving details of a specific user.

    The UserDetailView class is used to fetch and display the details of a
    specific user from the database. It ensures that only authenticated users
    can access the details through the implementation of permission classes.
    This view uses a serializer to format the response data.

    :ivar queryset: The queryset containing all User objects, used to retrieve
        the requested user from the database.
    :type queryset: QuerySet

    :ivar serializer_class: The serializer class used to serialize and format
        the User object for output.
    :type serializer_class: Serializer

    :ivar permission_classes: A list of permission classes that determine
        whether the requesting user is authorized to access this view.
    :type permission_classes: list
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class RegisterView(generics.CreateAPIView):
    """
    Handles user registration and token generation.

    This class is responsible for enabling user registration by processing the incoming
    request data, validating it, and saving a new user to the database if the data is
    valid. Upon successful registration, JWT tokens are generated and returned in the
    response to facilitate authentication.

    :ivar serializer_class: The serializer class used for validating and processing
                            incoming user data.
    :type serializer_class: type
    :ivar permission_classes: The list of permission classes that define access
                              restrictions for this view.
    :type permission_classes: list
    """
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request: Request, *args: list[Any], **kwargs: dict[str, Any]) -> Response:
        """
        Handles the creation of a new user and generates JWT tokens for authentication.

        This method validates incoming request data using a serializer, creates a new
        user if the data is valid, and generates JWT tokens (access and refresh) for
        the newly created user. The response contains the serialized user data and
        the generated tokens.

        :param request: The HTTP request object containing the user data to be
                        processed.
        :type request: Request
        :param args: Additional positional arguments that may be provided.
        :type args: list[Any]
        :param kwargs: Additional keyword arguments that may be provided.
        :type kwargs: dict[str, Any]
        :return: A Response object containing the serialized user data and JWT tokens.
        :rtype: Response
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # send the verification email
        send_verification_email(user)

        # generate JWT tokens for the newly created user
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user"  : RegisterSerializer(user).data,
                "tokens": {
                    "access" : str(refresh.access_token),
                    "refresh": str(refresh)
                }
            },
            status=status.HTTP_201_CREATED,
        )


# creating the verification email view
class VerifyEmailView(generics.GenericAPIView):
    """
    Handles the email verification process.

    This class-based view is responsible for verifying a user's email by processing
    a POST request. It uses a serializer to validate the request data and updates
    the user's verification status upon successful validation.

    :ivar serializer_class: The serializer class used to validate the request data.
    :type serializer_class: VerifyEmailSerializer
    :ivar permission_classes: The list of permission classes required to access this view.
    :type permission_classes: list
    """
    serializer_class = VerifyEmailSerializer
    permission_classes = [AllowAny]

    def post(self, request: Request, *args: list[Any], **kwargs: dict[str, Any]) -> Response:
        """
        Handles the POST request for email verification. Validates the request data using a serializer,
        marks the user as verified upon successful validation, and updates the `is_verified`
        attribute in the database.

        :param request: The HTTP request object containing the data to be validated.
        :type request: Request
        :param args: Additional positional arguments.
        :type args: list[Any]
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict[str, Any]
        :return: A Response object containing a success message and a 200 status code.
        :rtype: Response
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.is_verified = True
        user.save(update_fields=["is_verified"])

        return Response(
            {"detail": "Email verified successfully."},
            status=status.HTTP_200_OK,
        )


# resend the verification email, if the user is logged in, only
# work if the user is not only verified.
class ResendVerificationView(generics.GenericAPIView):
    """
    Handles resending verification emails for authenticated users.

    This view allows authenticated users who have not yet verified their email
    to request a new verification email to be sent. If the email is already
    verified, a response indicating that verification has already been completed
    is returned.

    :ivar permission_classes: Specifies the permissions required for accessing
        this view.
    :type permission_classes: list
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: list[Any], **kwargs: dict[str, Any]) -> Response:
        """
        Handles the HTTP POST request to send an email verification link to
        the user. If the user's email is already verified, it returns an
        appropriate error response. If the email is not verified, it triggers
        a verification email to be sent and returns a success response.

        :param request: Represents the HTTP request containing metadata
            about the request and user-related data.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: Response object containing status and detail message.
        :rtype: Response
        """
        user: User = request.user  # type: ignore[assignment]

        if user.is_verified:
            return Response(
                {"detail": "Email is already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_verification_email(user)

        return Response(
            {"detail": "Verification email sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(generics.GenericAPIView):
    """
    Handles the password reset request process.

    This class processes a user's request to reset their password. By validating the
    provided email address associated with a user account, it initiates the sending
    of a password reset link. If no account exists for the given email, the system
    responds uniformly to avoid revealing user existence. It is particularly useful
    in improving the security of user account recovery workflows.

    :ivar serializer_class: The serializer class used for validating password reset request data.
    :type serializer_class: Serializer class
    :ivar permission_classes: List of permission classes applied for this view.
    :type permission_classes: List of permissions
    """
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request: Request, *args: list[Any], **kwargs: dict[str, Any]) -> Response:
        """
        Handles the password reset process by validating the provided email and sending
        a password reset link to the associated user account, if it exists. If no user
        is found with the provided email, no error is raised, and the response is the
        same to prevent exposing user existence.

        :param request: The HTTP request containing the data for initiating password
            reset, including the email address to look up.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: A Response object with a message indicating that, if an account
            associated with the provided email address exists, a password reset link
            has been sent.
        :rtype: Response
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
            send_password_reset_email(user)
        except User.DoesNotExist:
            pass

        return Response(
            {
                "detail": (
                    "If an account with this email exists, "
                    "a password reset link has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Handles password reset confirmation functionality.

    This class is a generic API view that processes password reset confirmation
    requests. It ensures that the incoming data is validated through the
    associated serializer, updates the user's password, and provides a response
    indicating the success of the operation.

    :ivar serializer_class: The serializer class used for validating the incoming
        request data and extracting required fields for processing.
    :type serializer_class: PasswordResetConfirmSerializer
    :ivar permission_classes: Permission classes that specify access control for
        this view.
    :type permission_classes: list[type[AllowAny]]
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request: Request, *args: list[Any], **kwargs: dict[str, Any]) -> Response:
        """
        Handles POST requests for resetting a user's password. Validates the incoming data
        using the serializer, updates the user's password, and saves the changes to the
        database. Returns a success response upon completion.

        :param request: The HTTP request object containing user data.
        :type request: Request
        :param args: Additional positional arguments.
        :type args: list[Any]
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict[str, Any]
        :return: HTTP response indicating success of the password reset operation.
        :rtype: Response
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(generics.GenericAPIView):
    """
    Handles password change functionality for authenticated users.

    This class provides an endpoint where authenticated users can change their passwords.
    The password validation and update process is handled securely using a serializer.

    :ivar serializer_class: Serializer responsible for validating the input data for
        changing the password.
    :type serializer_class: type
    :ivar permission_classes: Permissions required to access this view. By default, this
        view is restricted to authenticated users.
    :type permission_classes: list[type]
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: list[Any], **kwargs: dict[str, Any]) -> Response:
        """
        Handles the logic for updating the user's password based on the provided request data.
        This method validates the input data using a serializer, updates the user's password
        if the data is valid, and responds with a success message upon successful completion.

        :param request: The HTTP request containing the password update data.
        :type request: Request
        :param args: Additional positional arguments passed to the method.
        :type args: list[Any]
        :param kwargs: Additional keyword arguments passed to the method.
        :type kwargs: dict[str, Any]
        :return: Returns a Response object containing a success message and HTTP 200 status
                 code if the password is updated successfully.
        :rtype: Response
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )
