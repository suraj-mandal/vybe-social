from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.posts.models import Post


class PostCommentTestBase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.charlie = User.objects.create_user(
            email="charlie@example.com",
            username="charlie",
            password="TestPass123!",
        )

        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
            responded_at=timezone.now(),
        )

        self.client: APIClient = APIClient()

    def _auth(self, user: User | None):
        self.client.force_authenticate(user=user)

    def _make_post(
        self,
        author: User = None,
        visibility: str = Post.Visibility.PUBLIC,
        content: str = "hello world",
    ):
        return Post.objects.create(
            author=author or self.alice,
            content=content,
            visibility=visibility,
        )
