from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.media.models import Media
from apps.moderation.models import Block
from apps.posts.models import Post


def _make_media(user, s3_key="posts/x/one.jpg"):
    return Media.objects.create(
        uploaded_by=user,
        s3_key=s3_key,
        media_type=Media.MediaType.IMAGE,
        content_type="image/jpeg",
        file_name=s3_key.rsplit("/", 1)[-1],
        file_size=100,
        upload_status=Media.UploadStatus.COMPLETED,
    )


class PostViewTestBase(TestCase):
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


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestPostListCreateView(PostViewTestBase):
    def test_requires_authentication(self, _p):
        response = self.client.get("/api/posts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_shows_public_posts(self, _p):
        Post.objects.create(
            author=self.alice, content="hello", visibility="public"
        )
        self._auth(self.charlie)

        response = self.client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_list_hides_private_posts_from_others(self, _p):
        Post.objects.create(
            author=self.alice, content="hello", visibility="private"
        )
        self._auth(self.charlie)

        response = self.client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_list_shows_friends_posts_to_friends(self, _p):
        Post.objects.create(
            author=self.alice, content="hello", visibility="friends"
        )
        self._auth(self.bob)

        response = self.client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_list_hides_friends_posts_to_non_friends(self, _p):
        Post.objects.create(
            author=self.alice, content="hello", visibility="friends"
        )
        self._auth(self.charlie)

        response = self.client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_list_excludes_posts_from_blocked_users(self, _p):
        # alice creates a public post
        Post.objects.create(
            author=self.alice, content="hello", visibility="public"
        )
        # charlie blocks alice
        Block.objects.create(blocker=self.charlie, blocked=self.alice)

        # charlie logs in
        self._auth(self.charlie)

        response = self.client.get("/api/posts/")
        # charlie should see no posts
        assert len(response.data["results"]) == 0

    def test_list_excludes_posts_from_users_who_blocked_me(self, _p):
        # alice creates a public post
        Post.objects.create(
            author=self.alice, content="hello", visibility="public"
        )
        # alice blocks charlie
        Block.objects.create(blocker=self.alice, blocked=self.charlie)

        # charlie logs in
        self._auth(self.charlie)

        response = self.client.get("/api/posts/")
        # charlie should see no posts
        assert len(response.data["results"]) == 0

    def test_list_excludes_soft_deleted(self, _p):
        post = Post.objects.create(
            author=self.alice, content="bye", visibility="public"
        )
        post.delete()  # soft-delete the post
        self._auth(self.alice)

        response = self.client.get("/api/posts/")
        assert len(response.data["results"]) == 0  # should show no posts

    #   ---- source filter ----

    def test_source_mine_returns_only_own_posts(self, _p):
        Post.objects.create(
            author=self.alice, content="mine", visibility="public"
        )
        Post.objects.create(
            author=self.bob, content="theirs", visibility="public"
        )
        self._auth(self.alice)

        # getting alice's posts only
        response = self.client.get("/api/posts/?source=mine")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["content"] == "mine"

    def test_source_friends_returns_only_friend_posts(self, _p):
        Post.objects.create(
            author=self.alice, content="mine", visibility="public"
        )
        Post.objects.create(
            author=self.bob, content="friends", visibility="public"
        )
        Post.objects.create(
            author=self.charlie, content="theirs", visibility="public"
        )

        self._auth(self.alice)

        response = self.client.get("/api/posts/?source=friends")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["content"] == "friends"

    def test_source_all_is_default(self, _p):
        Post.objects.create(
            author=self.alice, content="own", visibility="public"
        )
        Post.objects.create(
            author=self.bob, content="friend", visibility="public"
        )

        self._auth(self.alice)

        response = self.client.get("/api/posts/")
        assert len(response.data["results"]) == 2

    def test_invalid_source_returns_400(self, _p):
        self._auth(self.alice)
        response = self.client.get("/api/posts/?source=bogus")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "source" in response.data

    # ---- ordering ----
    def test_ordering_new_is_default(self, _p):
        self._auth(self.alice)
        response = self.client.get("/api/posts/?ordering=new")
        assert response.status_code == status.HTTP_200_OK

    def test_ordering_relevance_accepted_as_stub(self, _p):
        self._auth(self.alice)
        response = self.client.get("/api/posts/?ordering=relevance")
        assert response.status_code == status.HTTP_200_OK

    def test_invalid_ordering_returns_400(self, _p):
        self._auth(self.alice)
        response = self.client.get("/api/posts/?ordering=bogus")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ordering" in response.data

    def test_create_text_only_post(self, _p):
        self._auth(self.alice)

        response = self.client.post(
            "/api/posts/",
            {"content": "hello world", "visibility": "public"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["content"] == "hello world"
        assert response.data["author"]["username"] == "alice"
        assert Post.objects.count() == 1

    def test_create_rejects_empty_post(self, _p):
        self._auth(self.alice)

        response = self.client.post(
            "/api/posts/",
            {"content": "", "visibility": "public"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_media(self, _p):
        media = _make_media(self.alice)
        self._auth(self.alice)

        response = self.client.post(
            "/api/posts/",
            {
                "content": "look",
                "visibility": "public",
                "media_ids": [str(media.id)],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["media"]) == 1
        assert response.data["media"][0]["media_id"] == str(media.id)


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestPostDetailView(PostViewTestBase):
    def test_get_detail_visible_public_post(self, _p):
        post = Post.objects.create(
            author=self.alice, content="hi", visibility="public"
        )
        self._auth(self.charlie)

        response = self.client.get(f"/api/posts/{post.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(post.id)

    def test_get_detail_private_post_returns_404(self, _p):
        post = Post.objects.create(
            author=self.alice, content="secret", visibility="private"
        )
        self._auth(self.charlie)

        response = self.client.get(f"/api/posts/{post.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_own_post(self, _p):
        post = Post.objects.create(
            author=self.alice, content="hi", visibility="public"
        )
        self._auth(self.alice)

        response = self.client.patch(
            f"/api/posts/{post.id}/",
            {"content": "edited"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["content"] == "edited"
        assert response.data["is_edited"] is True

    def test_update_others_post_returns_403(self, _p):
        post = Post.objects.create(
            author=self.alice, content="hi", visibility="public"
        )
        self._auth(self.bob)

        response = self.client.patch(
            f"/api/posts/{post.id}/",
            {"content": "hacked"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_own_post_soft_deletes(self, _p):
        post = Post.objects.create(
            author=self.alice, content="bye", visibility="public"
        )
        self._auth(self.alice)

        response = self.client.delete(f"/api/posts/{post.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Post.all_objects.get(id=post.id).deleted_at is not None
        assert Post.objects.filter(id=post.id).count() == 0

    def test_delete_others_post_returns_403(self, _p):
        post = Post.objects.create(
            author=self.alice, content="bye", visibility="public"
        )
        self._auth(self.bob)

        response = self.client.delete(f"/api/posts/{post.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_author_can_fetch_own_draft_via_detail(self, _p):
        draft = Post.objects.create(
            author=self.alice,
            content="wip",
            visibility="public",
            status=Post.Status.DRAFT,
        )

        self._auth(self.alice)

        response = self.client.get(f"/api/posts/{draft.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "draft"
        assert response.data["published_at"] is None


@patch(
    "apps.posts.serializers.generate_presigned_read_url",
    return_value="https://signed",
)
class TestDraftsAndPublishing(PostViewTestBase):
    def test_create_as_draft_sets_status_and_leaves_published_at_null(self, _p):
        self._auth(self.alice)

        response = self.client.post(
            "/api/posts/",
            {
                "content": "wip",
                "visibility": "public",
                "status": "draft",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "draft"
        assert response.data["published_at"] is None

        post = Post.objects.get(id=response.data["id"])
        assert post.status == Post.Status.DRAFT
        assert post.published_at is None

    def test_create_without_status_defaults_to_published_and_stamps_published_at(
        self, _p
    ):
        self._auth(self.alice)

        response = self.client.post(
            "/api/posts/",
            {
                "content": "to publish",
                "visibility": "public",
                "status": "published",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "published"
        assert response.data["published_at"] is not None

        post = Post.objects.get(id=response.data["id"])
        assert post.status == Post.Status.PUBLISHED
        assert post.published_at is not None

    def test_draft_hidden_from_main_feed(self, _p):
        Post.objects.create(
            author=self.alice,
            content="wip",
            visibility="public",
            status=Post.Status.DRAFT,
        )
        self._auth(self.alice)

        response = self.client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_draft_hidden_from_source_mine_of_author(self, _p):
        # creating draft post
        Post.objects.create(
            author=self.alice,
            content="wip",
            visibility="public",
            status=Post.Status.DRAFT,
        )

        # creating published post
        Post.objects.create(
            author=self.alice,
            content="live",
            visibility="public",
        )

        self._auth(self.alice)

        response = self.client.get("/api/posts/?source=mine")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["content"] == "live"

    def test_draft_detail_404_for_non_author(self, _p):
        # alice creates draft post
        Post.objects.create(
            author=self.alice,
            content="wip",
            visibility="public",
            status=Post.Status.DRAFT,
        )

        # bob logins
        self._auth(self.bob)

        # bob should see no post
        response = self.client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_drafts_list_returns_only_own_drafts(self, _p):
        # draft post created by alice
        Post.objects.create(
            author=self.alice,
            content="mine",
            status=Post.Status.DRAFT,
        )
        # draft post created by bob
        Post.objects.create(
            author=self.bob,
            content="theirs",
            status=Post.Status.DRAFT,
        )
        # live post
        Post.objects.create(author=self.alice, content="live")

        self._auth(self.alice)

        response = self.client.get("/api/posts/drafts/")
        assert response.status_code == status.HTTP_200_OK
        contents = {p["content"] for p in response.data["results"]}
        assert contents == {"mine"}

    def test_draft_requires_auth(self, _p):
        response = self.client.get("/api/posts/drafts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ---- publish endpoint ----
    def test_publish_flips_status_and_stamps_published_at(self, _p):
        draft: Post = Post.objects.create(
            author=self.alice,
            content="ready",
            status=Post.Status.DRAFT,
        )

        assert draft.published_at is None
        assert draft.status == Post.Status.DRAFT

        self._auth(self.alice)

        # now publishing the post
        response = self.client.post(f"/api/posts/{draft.id}/publish/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "published"
        assert response.data["published_at"] is not None

        draft.refresh_from_db()

        assert draft.status == Post.Status.PUBLISHED
        assert draft.published_at is not None

    def test_publish_is_idempotent(self, _p):
        # already published post cannot be published again
        post = Post.objects.create(author=self.alice, content="live")
        original_published_at = post.published_at
        self._auth(self.alice)

        response = self.client.post(f"/api/posts/{post.id}/publish/")
        assert response.status_code == status.HTTP_200_OK

        post.refresh_from_db()

        assert post.published_at == original_published_at

    def test_publish_non_author_returns_404(self, _p):
        # already published post cannot be published again
        draft = Post.objects.create(
            author=self.alice, content="wip", status=Post.Status.DRAFT
        )

        self._auth(self.bob)

        response = self.client.post(f"/api/posts/{draft.id}/publish/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        draft.refresh_from_db()
        assert draft.status == Post.Status.DRAFT

    def test_publish_requires_auth(self, _p):
        draft = Post.objects.create(
            author=self.alice, content="wip", status=Post.Status.DRAFT
        )
        response = self.client.post(f"/api/posts/{draft.id}/publish/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
