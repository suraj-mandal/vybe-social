from collections.abc import Iterable

from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Profile
from .serializers import ProfileSerializer


class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> Profile | None:
        return Profile.objects.select_related("user", "avatar").get(user=self.request.user)


class PublicProfileDetailView(generics.RetrieveAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "user__username"
    lookup_url_kwarg = "username"

    def get_queryset(self) -> Iterable[Profile]:
        return Profile.objects.select_related("user", "avatar")
