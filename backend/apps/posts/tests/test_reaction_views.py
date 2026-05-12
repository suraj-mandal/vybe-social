from unittest.mock import patch

from rest_framework import status

from apps.posts.models import Comment, Post, Reaction
from apps.posts.tests._base import PostCommentTestBase


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestPostReactionView(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        self.post = self._make_post(author=self.alice)
        self.url = f"/api/posts/{self.post.pk}/reactions/"

    def test_requires_auth(self, _p):
        response = self.client.post(self.url, {"type": "heart"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_new_reaction(self, _p):
        self._auth(self.bob)
        response = self.client.post(self.url, {"type": "heart"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Reaction.objects.filter(user=self.bob).count() == 1

    def test_same_type_is_idempotent_200(self, _p):
        self._auth(self.bob)
        self.client.post(self.url, {"type": "heart"}, format="json")
        response = self.client.post(self.url, {"type": "heart"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert Reaction.objects.filter(user=self.bob).count() == 1

    def test_different_type_updates_to_200(self, _p):
        self._auth(self.bob)
        self.client.post(self.url, {"type": "heart"}, format="json")
        response = self.client.post(self.url, {"type": "haha"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        r = Reaction.objects.get(user=self.bob)

        assert r.type == Reaction.Type.HAHA

    def test_invalid_type_400(self, _p):
        self._auth(self.bob)
        response = self.client.post(self.url, {"type": "scream"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_existing(self, _p):
        self._auth(self.bob)
        self.client.post(self.url, {"type": "heart"}, format="json")

        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Reaction.objects.filter(user=self.bob).count() == 0

    def test_delete_nonexistent_is_idempotent(self, _p):
        self._auth(self.bob)
        response = self.client.delete(
            self.url
        )  # there should be no reactions given
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_cannot_react_on_invisible_post(self, _p):
        private = self._make_post(
            author=self.alice, visibility=Post.Visibility.PRIVATE
        )

        self._auth(self.charlie)
        response = self.client.post(
            f"/api/posts/{private.pk}/reactions/",
            {"type": "heart"},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# testing reaction on comments present in the post
@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestCommentReactionView(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        self.post = self._make_post(author=self.alice)
        self.comment = Comment.objects.create(
            post=self.post, user=self.bob, content="hey"
        )
        self.url = f"/api/comments/{self.comment.pk}/reactions/"

    def test_react_on_comment_of_visible_post(self, _p):
        self._auth(self.charlie)
        response = self.client.post(self.url, {"type": "heart"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_react_on_comment_of_invisible_post(self, _p):
        private = self._make_post(
            author=self.alice,
            visibility=Post.Visibility.PRIVATE,
        )
        comment = Comment.objects.create(
            post=private, user=self.alice, content="x"
        )
        self._auth(self.charlie)
        response = self.client.post(
            f"/api/comments/{comment.pk}/reactions/",
            {"type": "heart"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_post_and_comments_reactions_independent(self, _p):
        self._auth(self.charlie)

        # reacting to the post
        self.client.post(
            f"/api/posts/{self.post.pk}/reactions/",
            {"type": "like"},
            format="json",
        )

        # reacting to the comment
        self.client.post(self.url, {"type": "heart"}, format="json")

        # one reaction will be for the post.
        # one reaction will be for the reaction.
        assert Reaction.objects.filter(user=self.charlie).count() == 2


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestPostReactionsListView(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        self.post = self._make_post(author=self.alice)
        # reacting to the post
        Reaction.objects.create(
            user=self.bob, target=self.post, type=Reaction.Type.HEART
        )
        Reaction.objects.create(
            user=self.charlie, target=self.post, type=Reaction.Type.HAHA
        )
        self.url = f"/api/posts/{self.post.pk}/reactions/list/"

    def test_list_returns_paginated(self, _p):
        self._auth(self.bob)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_filter_by_type(self, _p):
        self._auth(self.bob)
        response = self.client.get(f"{self.url}?type=heart")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["type"] == "heart"

    def test_invalid_type(self, _p):
        self._auth(self.bob)
        response = self.client.get(f"{self.url}?type=scream")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
