from typing import Any

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .emails import send_verification_email
from .models import User
from .serializers import UserSerializer, RegisterSerializer, VerifyEmailSerializer


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
