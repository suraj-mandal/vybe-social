from unittest.mock import patch

from django.conf import settings
from rest_framework import status

from apps.posts.models import Comment, Post
from apps.posts.tests._base import PostCommentTestBase


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestCommentRepliesView(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        self.post = self._make_post(author=self.alice)
        self.parent = Comment.objects.create(
            post=self.post, user=self.bob, content="p"
        )

    def test_paginated_newest_first(self, _p):
        older = Comment.objects.create(
            post=self.post, user=self.alice, content="old", parent=self.parent
        )

        newer = Comment.objects.create(
            post=self.post, user=self.alice, content="new", parent=self.parent
        )

        self._auth(self.bob)

        response = self.client.get(f"/api/comments/{self.parent.pk}/replies/")

        ids = [r["id"] for r in response.data["results"]]

        assert response.status_code == status.HTTP_200_OK
        assert ids.index(str(newer.pk)) < ids.index(str(older.pk))

    def test_walks_whole_thread_across_pages(self, _p):
        n = settings.REPLIES_PAGE_SIZE * 3

        for i in range(n):
            Comment.objects.create(
                post=self.post,
                user=self.alice,
                content=f"r{i}",
                parent=self.parent,
            )

        self._auth(self.bob)

        response = self.client.get(f"/api/comments/{self.parent.pk}/replies/")
        assert len(response.data["results"]) == settings.REPLIES_PAGE_SIZE
        assert response.data["next"] is not None

    def test_parent_not_top_level_404(self, _p):
        reply = Comment.objects.create(
            post=self.post, user=self.alice, content="r", parent=self.parent
        )
        self._auth(self.bob)

        response = self.client.get(f"/api/comments/{reply.pk}/replies/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_parent_post_invisible_404(self, _p):
        private = self._make_post(
            author=self.alice, visibility=Post.Visibility.PRIVATE
        )

        parent = Comment.objects.create(
            post=private, user=self.alice, content="p"
        )

        self._auth(self.charlie)

        response = self.client.get(f"/api/comments/{parent.pk}/replies/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
