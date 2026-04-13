from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.posts.models import Post
from apps.posts.permissions import IsAuthorOrReadOnly


class TestIsAuthorOrReadOnly(TestCase):
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

        self.post = Post.objects.create(author=self.alice, content="hi")
        self.factory = RequestFactory()
        self.permission = IsAuthorOrReadOnly()

    def _req(self, method, user):
        request = getattr(self.factory, method.lower())("/api/posts/")
        request.user = user
        return request

    def test_unauthenticated_denied(self):
        request = self._req("GET", None)
        assert self.permission.has_permission(request, None) is False

    def test_safe_method_allowed_for_non_author(self):
        request = self._req("GET", self.bob)
        assert (
            self.permission.has_object_permission(request, None, self.post)
            is True
        )

    def test_unsafe_method_denied_for_non_author(self):
        request = self._req("PATCH", self.bob)
        assert (
            self.permission.has_object_permission(request, None, self.post)
            is False
        )

    def test_unsafe_method_allowed_for_author(self):
        request = self._req("PATCH", self.alice)
        assert (
            self.permission.has_object_permission(request, None, self.post)
            is True
        )
