from unittest.mock import MagicMock

from rest_framework.test import APIRequestFactory

from apps.posts.models import Post
from apps.posts.permissions import CanCommentOnPost, IsAuthorOrReadOnly
from apps.posts.tests._base import PostCommentTestBase


class TestCanCommentOnPost(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        self.perm = CanCommentOnPost()
        self.factory = APIRequestFactory()

    def _req(self, user):
        r = self.factory.post("/")
        r.user = user
        return r

    def test_public_allows_anyone(self):
        post = self._make_post(author=self.alice)
        assert self.perm.has_object_permission(
            self._req(self.charlie), MagicMock(), post
        )

    def test_friends_allow_friend(self):
        post = self._make_post(
            author=self.alice, visibility=Post.Visibility.FRIENDS
        )
        assert self.perm.has_object_permission(
            self._req(self.bob), MagicMock(), post
        )

    def test_friends_allows_author(self):
        post = self._make_post(
            author=self.alice, visibility=Post.Visibility.FRIENDS
        )
        assert self.perm.has_object_permission(
            self._req(self.alice), MagicMock(), post
        )

    def test_friends_denies_non_friend(self):
        post = self._make_post(
            author=self.alice, visibility=Post.Visibility.FRIENDS
        )
        assert not self.perm.has_object_permission(
            self._req(self.charlie), MagicMock(), post
        )

    def test_private_denies_everyone_including_author(self):
        post = self._make_post(
            author=self.alice, visibility=Post.Visibility.PRIVATE
        )
        assert not self.perm.has_object_permission(
            self._req(self.charlie), MagicMock(), post
        )

        assert not self.perm.has_object_permission(
            self._req(self.alice), MagicMock(), post
        )


class TestIsAuthorOrReadOnly(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        from apps.posts.models import Comment

        self.post = self._make_post(author=self.alice)
        self.comment = Comment.objects.create(
            post=self.post,
            user=self.bob,
            content="hi",
        )
        self.perm = IsAuthorOrReadOnly()
        self.factory = APIRequestFactory()

    def _req(self, method, user):
        r = getattr(self.factory, method.lower())("/")
        r.user = user
        return r

    def test_read_allowed_for_any_user(self):
        assert self.perm.has_object_permission(
            self._req("GET", self.charlie),
            MagicMock(),
            self.comment,
        )

    def test_write_only_for_comment_user(self):
        assert self.perm.has_object_permission(
            self._req("PATCH", self.bob), MagicMock(), self.comment
        )

        assert not self.perm.has_object_permission(
            self._req("PATCH", self.alice),
            MagicMock(),
            self.comment,
        )
