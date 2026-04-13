from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.media.models import Media
from apps.moderation.models import Block
from apps.posts.models import Post, PostMedia
from apps.posts.selectors import visible_posts_for


def _make_media(
    user: User,
    s3_key: str = "posts/abc/one.jpg",
    media_type: Media.MediaType = Media.MediaType.IMAGE,
    status: Media.UploadStatus = Media.UploadStatus.COMPLETED,
    file_size: int = 123456,
):
    return Media.objects.create(
        uploaded_by=user,
        s3_key=s3_key,
        media_type=media_type,
        content_type="image/jpeg"
        if media_type == Media.MediaType.IMAGE
        else "video/mp4",
        file_name=s3_key.rsplit("/", 1)[-1],
        file_size=file_size,
        upload_status=status,
    )


class TestPostModel(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", username="alice", password="TestPass123!"
        )

    def test_create_post_with_defaults(self):
        post = Post.objects.create(author=self.alice, content="hello")

        assert post.visibility == Post.Visibility.PUBLIC
        assert post.adult_rating == Post.AdultRating.UNCLASSIFIED
        assert post.is_edited is False
        assert post.deleted_at is None
        assert post.status == Post.Status.PUBLISHED

    def test_post_str(self):
        post = Post.objects.create(author=self.alice, content="hello world")
        assert "alice" in str(post)

    def test_post_str_without_content(self):
        post = Post.objects.create(author=self.alice, content="")
        assert "media" in str(post)

    def test_soft_delete_sets_deleted_at(self):
        post = Post.objects.create(author=self.alice, content="bye")
        post.delete()

        # row exists as per the manager
        assert Post.all_objects.filter(id=post.id).exists()

        # default manager will hide the post
        assert not Post.objects.filter(id=post.id).exists()

        row: Post = Post.all_objects.get(id=post.id)
        assert row.deleted_at is not None

    def test_hard_delete_removes_rows(self):
        post = Post.objects.create(author=self.alice, content="gone")
        post.hard_delete()

        assert not Post.all_objects.filter(id=post.id).exists()

    def test_reverse_relation_excludes_soft_deleted(self):
        Post.objects.create(author=self.alice, content="one")
        deleted: Post = Post.objects.create(author=self.alice, content="two")
        deleted.delete()

        assert self.alice.posts.count() == 1  # should not show the deleted post


class TestPostMediaModel(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )

        self.post = Post.objects.create(author=self.alice, content="")

    def test_create_postmedia_references_media(self):
        media = _make_media(self.alice)

        pm: PostMedia = PostMedia.objects.create(
            post=self.post,
            media=media,
            position=0,
        )

        assert pm.id is not None
        assert pm.post == self.post
        assert pm.media == media
        assert pm.media.s3_key == "posts/abc/one.jpg"
        assert pm.media.media_type == Media.MediaType.IMAGE

    def test_cascade_delete_removes_join_but_keeps_media(self):
        media = _make_media(self.alice, s3_key="posts/abc/keeper.jpg")
        PostMedia.objects.create(post=self.post, media=media, position=0)

        self.post.hard_delete()
        assert PostMedia.objects.count() == 0

        assert Media.objects.filter(id=media.id).exists()

    def test_protect_prevents_deleting_referenced_media(self):
        media = _make_media(self.alice, s3_key="posts/abc/shielded.jpg")
        PostMedia.objects.create(post=self.post, media=media, position=0)

        with self.assertRaises(IntegrityError):
            media.delete()

    def test_unique_together_rejects_duplicate_attachment(self):
        media = _make_media(self.alice)
        PostMedia.objects.create(
            post=self.post,
            media=media,
            position=0,
        )

        with self.assertRaises(IntegrityError):
            PostMedia.objects.create(
                post=self.post,
                media=media,
                position=1,
            )

    def test_ordering_by_position(self):
        media_one = _make_media(self.alice)
        media_two = _make_media(self.alice, s3_key="posts/abc/two.jpg")
        media_three = _make_media(self.alice, s3_key="posts/abc/three.jpg")

        PostMedia.objects.create(
            post=self.post,
            media=media_one,
            position=2,
        )
        PostMedia.objects.create(
            post=self.post,
            media=media_two,
            position=0,
        )
        PostMedia.objects.create(
            post=self.post,
            media=media_three,
            position=1,
        )

        keys = [pm.media.s3_key for pm in self.post.media.all()]

        assert keys == [
            "posts/abc/two.jpg",
            "posts/abc/three.jpg",
            "posts/abc/one.jpg",
        ]


class TestVisibleForSelector(TestCase):
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

        # alice and bob become friends
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
            responded_at=timezone.now(),
        )

    def _make_post(self, author: User, visibility: Post.Visibility):
        return Post.objects.create(
            author=author,
            visibility=visibility,
            content=f"{author.username}-{visibility}",
        )

    def test_public_post_visible_to_everyone(self):
        post = self._make_post(self.alice, Post.Visibility.PUBLIC)

        assert visible_posts_for(self.bob).filter(id=post.id).exists()
        assert visible_posts_for(self.charlie).filter(id=post.id).exists()

    def test_friends_post_visible_to_friends_only(self):
        post = self._make_post(self.alice, Post.Visibility.FRIENDS)

        assert (
            visible_posts_for(self.bob).filter(id=post.id).exists()
        )  # Bob can see, since they are friends
        assert (
            not visible_posts_for(self.charlie).filter(id=post.id).exists()
        )  # Charlie cannot see

    def test_private_post_visible_to_author_only(self):
        post = self._make_post(self.alice, Post.Visibility.PRIVATE)

        assert (
            visible_posts_for(self.alice).filter(id=post.id).exists()
        )  # Alice can see their post
        assert (
            not visible_posts_for(self.bob).filter(id=post.id).exists()
        )  # Bob cannot see private post
        assert (
            not visible_posts_for(self.charlie).filter(id=post.id).exists()
        )  # Charlie cannot see

    def test_blocked_user_posts_hidden_from_blocker(self):
        post = self._make_post(self.alice, Post.Visibility.PUBLIC)
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        # Bob should not see Alice's post since he is blocked
        assert not visible_posts_for(self.bob).filter(id=post.id).exists()

    def test_soft_deleted_post_excluded(self):
        post = self._make_post(self.alice, Post.Visibility.PUBLIC)
        post.delete()

        assert not visible_posts_for(self.alice).filter(id=post.id).exists()
        assert not visible_posts_for(self.bob).filter(id=post.id).exists()
