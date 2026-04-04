from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import User
from .serializers import UserSerializer

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
