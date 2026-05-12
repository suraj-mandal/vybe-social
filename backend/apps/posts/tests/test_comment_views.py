from unittest.mock import patch

from django.conf import settings
from rest_framework import status

from apps.posts.mentions import sync_mentions
from apps.posts.models import Comment, CommentMention, Post
from apps.posts.tests._base import PostCommentTestBase


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestCommentsList(PostCommentTestBase):
    def test_lists_top_level_paginated(self, _p):
        post = self._make_post(author=self.alice)
        for i in range(12):
            Comment.objects.create(post=post, user=self.bob, content=f"c{i}")

        self._auth(self.bob)
        response = self.client.get(f"/api/posts/{post.pk}/comments/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 10  # COMMENTS_PAGE_SIZE
        assert response.data["next"] is not None

    def test_inline_replies_capped(self, _p):
        post = self._make_post(author=self.alice)
        parent = Comment.objects.create(post=post, user=self.bob, content="p")
        for i in range(12):
            Comment.objects.create(
                post=post, user=self.alice, content=f"r{i}", parent=parent
            )

        self._auth(self.bob)
        response = self.client.get(f"/api/posts/{post.pk}/comments/")
        row = response.data["results"][0]

        assert len(row["replies"]) == settings.REPLIES_INLINE_PREVIEW
        assert row["replies_count"] == 12

    def test_soft_deleted_top_level_excluded(self, _p):
        post = self._make_post()
        gone = Comment.objects.create(post=post, user=self.bob, content="bye")
        gone.delete()

        self._auth(self.bob)
        response = self.client.get(f"/api/posts/{post.pk}/comments/")
        assert response.data["results"] == []

    def test_list_on_invisible_post_404(self, _p):
        private = self._make_post(
            author=self.alice, visibility=Post.Visibility.PRIVATE
        )

        self._auth(self.charlie)
        response = self.client.get(f"/api/posts/{private.pk}/comments/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestPostCommentsCreate(PostCommentTestBase):
    def test_create_top_level_on_public_post(self, _p):
        post = self._make_post(author=self.alice)
        self._auth(self.charlie)

        response = self.client.post(
            f"/api/posts/{post.pk}/comments/",
            {"content": "hey @alice"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.filter(post=post).count() == 1
        assert CommentMention.objects.filter(user=self.alice).count() == 1

    def test_cannot_comment_on_private_post_even_as_author(self, _p):
        post = self._make_post(
            author=self.alice, visibility=Post.Visibility.PRIVATE
        )
        self._auth(self.alice)

        response = self.client.post(
            f"/api/posts/{post.pk}/comments/",
            {"content": "note"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_comment_on_friends_post_as_non_friend(self, _p):
        post = self._make_post(
            author=self.alice, visibility=Post.Visibility.FRIENDS
        )
        self._auth(self.charlie)

        response = self.client.post(
            f"/api/posts/{post.pk}/comments/",
            {"content": "note"},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_reply(self, _p):
        post = self._make_post(author=self.alice)
        parent = Comment.objects.create(post=post, user=self.alice, content="p")
        self._auth(self.bob)

        response = self.client.post(
            f"/api/posts/{post.pk}/comments/",
            {"content": "reply", "parent": str(parent.pk)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        reply = Comment.objects.get(content="reply")

        assert reply.parent_id == parent.id

    def test_reply_to_reply_rejected(self, _p):
        post = self._make_post(author=self.alice)
        parent = Comment.objects.create(post=post, user=self.alice, content="p")
        reply = Comment.objects.create(
            post=post, user=self.bob, content="r", parent=parent
        )

        self._auth(self.alice)

        response = self.client.post(
            f"/api/posts/{post.pk}/comments/",
            {"content": "nope", "parent": str(reply.pk)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cross_post_parent_rejected(self, _p):
        a = self._make_post(author=self.alice, content="A")
        b = self._make_post(author=self.alice, content="B")

        parent_on_a = Comment.objects.create(
            post=a, user=self.alice, content="pa"
        )

        self._auth(self.bob)

        # here bob will try to reply to a comment on post b, with the parent being a comment
        # on post a, which should not work
        response = self.client.post(
            f"/api/posts/{b.pk}/comments/",
            {"content": "nope", "parent": str(parent_on_a.pk)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_soft_deleted_parent_rejected(self, _p):
        post = self._make_post(author=self.alice)
        parent = Comment.objects.create(post=post, user=self.alice, content="p")
        parent.delete()  # delete the parent

        self._auth(self.bob)

        response = self.client.post(
            f"/api/posts/{post.pk}/comments/",
            {"content": "reply", "parent": str(parent.pk)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_mention_silently_ignored(self, _p):
        post = self._make_post(author=self.alice)
        self._auth(self.bob)

        response = self.client.post(
            f"/api/posts/{post.pk}/comments/",
            {"content": "hi @ghost"},
            format="json",
        )

        # will be created normally
        assert response.status_code == status.HTTP_201_CREATED

        # no comment mention object will be created since there is no user with username
        # ghost
        assert CommentMention.objects.count() == 0


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestCommentDetailView(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        self.post = self._make_post(author=self.alice)
        self.comment: Comment = Comment.objects.create(
            post=self.post, user=self.bob, content="original"
        )
        self.url = f"/api/comments/{self.comment.pk}/"

    def test_patch_by_author_flips_is_edited(self, _p):
        self._auth(self.bob)  # bob can edit the comment
        response = self.client.patch(
            self.url, {"content": "new"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

        self.comment.refresh_from_db()

        assert self.comment.content == "new"
        assert self.comment.is_edited is True

    def test_patch_identical_content_does_not_flip_is_edited(self, _p):
        self._auth(self.bob)
        response = self.client.patch(
            self.url, {"content": "original"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

        self.comment.refresh_from_db()

        assert self.comment.is_edited is False

    def test_patch_resyncs_mentions(self, _p):
        self.comment.content = "@alice"
        self.comment.save()

        sync_mentions(self.comment)

        assert self.comment.mentions.filter(user=self.alice).exists()

        self._auth(self.bob)
        self.client.patch(
            self.url, {"content": "@charlie instead"}, format="json"
        )

        mention_user_ids = set(
            self.comment.mentions.values_list("user_id", flat=True)
        )

        assert mention_user_ids == {self.charlie.id}

    def test_patch_by_non_author_forbidden(self, _p):
        self._auth(self.alice)
        response = self.client.patch(
            self.url, {"content": "hax"}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_by_author_soft_deletes(self, _p):
        self._auth(self.bob)
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        row: Comment = Comment.all_objects.get(pk=self.comment.pk)

        assert row.is_deleted is True
        assert row.content == ""

    def test_delete_preserves_replies(self, _p):
        reply = Comment.objects.create(
            post=self.post,
            user=self.alice,
            content="reply",
            parent=self.comment,
        )

        self._auth(self.bob)
        self.client.delete(self.url)

        assert Comment.objects.filter(pk=reply.pk).exists()

    def test_delete_by_non_author_forbidden(self, _p):
        self._auth(self.alice)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_renders_soft_deleted_as_placeholder(self, _p):
        self.comment.delete()

        self._auth(self.bob)
        response = self.client.get(f"/api/posts/{self.post.pk}/comments/")
        assert all(
            c["id"] != str(self.comment.pk) for c in response.data["results"]
        )
