from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.media.models import Media
from apps.posts.models import Post, PostMedia
from apps.posts.serializers import (
    PostCreateSerializer,
    PostMediaSerializer,
    PostSerializer,
    PostUpdateSerializer,
)


def _make_media(
    user: User,
    s3_key: str = "posts/abc/one.jpg",
    media_type: Media.MediaType = Media.MediaType.IMAGE,
    status: Media.UploadStatus = Media.UploadStatus.COMPLETED,
    file_size: int = 1000,
    content_type: str = "image/jpeg",
):
    return Media.objects.create(
        uploaded_by=user,
        s3_key=s3_key,
        media_type=media_type,
        content_type=content_type,
        file_name=s3_key.rsplit("/", 1)[-1],
        file_size=file_size,
        upload_status=status,
    )


class TestPostMediaSerializer(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )

        self.post = Post.objects.create(
            author=self.alice,
            content="hi",
        )

        self.underlying = _make_media(self.alice)
        self.postmedia_object = PostMedia.objects.create(
            post=self.post,
            media=self.underlying,
            position=0,
        )

    @patch("apps.posts.serializers.generate_presigned_read_url")
    def test_serializers_media_with_presigned_url(
        self, mock_presign: MagicMock
    ):
        mock_presign.return_value = "https://s3.example/signed"

        data = PostMediaSerializer(self.postmedia_object).data

        assert data["id"] == str(self.postmedia_object.id)
        assert data["media_id"] == str(self.underlying.id)
        assert data["media_type"] == "image"
        assert data["content_type"] == "image/jpeg"
        assert data["size"] == 1000
        assert data["position"] == 0
        assert data["url"] == "https://s3.example/signed"
        mock_presign.assert_called_once_with("posts/abc/one.jpg")


class TestPostSerializer(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
            first_name="Alice",
            last_name="Smith",
        )

        self.post = Post.objects.create(
            author=self.alice,
            content="hello_world",
            visibility=Post.Visibility.PUBLIC,
        )

    @patch("apps.posts.serializers.generate_presigned_read_url")
    def test_serializes_post_with_author_and_empty_media(self, _mock_presign):
        data = PostSerializer(self.post).data

        assert data["id"] == str(self.post.id)
        assert data["content"] == "hello_world"
        assert data["visibility"] == "public"
        assert data["author"]["id"] == str(self.alice.id)
        assert data["author"]["username"] == "alice"
        assert data["author"]["first_name"] == "Alice"
        assert data["author"]["last_name"] == "Smith"
        assert data["status"] == "published"
        assert data["is_edited"] is False
        assert data["media"] == []

    @patch("apps.posts.serializers.generate_presigned_read_url")
    def test_serializes_post_with_media(self, mock_presign: MagicMock):
        mock_presign.return_value = "https://signed"
        underlying = _make_media(self.alice, s3_key="posts/abc/a.jpg")
        PostMedia.objects.create(post=self.post, media=underlying, position=0)

        data = PostSerializer(self.post).data
        assert len(data["media"]) == 1
        assert data["media"][0]["url"] == "https://signed"


class TestPostCreateSerializer(TestCase):
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
        self.factory = RequestFactory()
        self.request = self.factory.post("/api/posts/")
        self.request.user = self.alice

    def _context(self):
        return {"request": self.request}

    def test_rejects_empty_post(self):
        serializer = PostCreateSerializer(
            data={"content": "", "media_ids": []}, context=self._context()
        )
        assert not serializer.is_valid()
        assert "either text content" in str(serializer.errors)

    def test_accepts_text_only_post(self):
        serializer = PostCreateSerializer(
            data={"content": "hi", "media_ids": []}, context=self._context()
        )
        assert serializer.is_valid(), serializer.errors

    def test_rejects_duplicate_media_ids(self):
        media = _make_media(self.alice, s3_key="posts/abc/dup.jpg")
        serializer = PostCreateSerializer(
            data={"content": "hi", "media_ids": [str(media.id), str(media.id)]},
        )
        assert not serializer.is_valid()
        assert "Duplicate" in str(serializer.errors)

    def test_rejects_too_many_images(self):
        image_limit = settings.POSTS_MAX_IMAGES_PER_POST
        ids = [
            str(_make_media(self.alice, s3_key=f"posts/abc/{i}.jpg").id)
            for i in range(image_limit + 1)
        ]
        serializer = PostCreateSerializer(
            data={"content": "", "media_ids": ids}, context=self._context()
        )
        assert not serializer.is_valid()
        assert f"at most {image_limit} images" in str(serializer.errors)

    def test_rejects_too_many_videos(self):
        video_limit = settings.POSTS_MAX_VIDEOS_PER_POST
        ids = [
            str(
                _make_media(
                    self.alice,
                    s3_key=f"posts/abc/{i}.mp4",
                    media_type=Media.MediaType.VIDEO,
                    content_type="video/mp4",
                ).id
            )
            for i in range(video_limit + 1)
        ]
        serializer = PostCreateSerializer(
            data={"content": "", "media_ids": ids}, context=self._context()
        )
        assert not serializer.is_valid()
        assert f"at most {video_limit} videos" in str(serializer.errors)

    def test_creates_post_with_media(self):
        media = _make_media(self.alice, s3_key="posts/x/one.jpg")

        serializer = PostCreateSerializer(
            data={
                "content": "hello",
                "visibility": "public",
                "media_ids": [
                    str(media.id),
                ],
            },
            context=self._context(),
        )

        assert serializer.is_valid(), serializer.errors
        post = serializer.save()

        assert post.author == self.alice
        assert post.content == "hello"
        assert post.media.count() == 1

        pm = post.media.first()
        assert pm.media_id == media.id
        assert pm.media.s3_key == "posts/x/one.jpg"
        assert pm.position == 0

    def test_bulk_create_preserves_client_order_as_position(self):
        first = _make_media(self.alice, s3_key="posts/x/first.jpg")
        second = _make_media(self.alice, s3_key="posts/x/second.jpg")
        third = _make_media(self.alice, s3_key="posts/x/third.jpg")

        serializer = PostCreateSerializer(
            data={
                "content": "hi",
                # deliberately out of creation order
                "media_ids": [str(third.id), str(first.id), str(second.id)],
            },
            context=self._context(),
        )
        assert serializer.is_valid(), serializer.errors
        post = serializer.save()

        ordered = list(
            post.media.all()
        )  # Meta.ordering is ["position", "created_at"]
        assert [pm.media_id for pm in ordered] == [
            third.id,
            first.id,
            second.id,
        ]
        assert [pm.position for pm in ordered] == [0, 1, 2]

    def test_rejects_media_owned_by_another_user(self):
        # Bob uploaded it, Alice tries to attach it.
        media = _make_media(self.bob, s3_key="posts/bob/stolen.jpg")
        serializer = PostCreateSerializer(
            data={"content": "hi", "media_ids": [str(media.id)]},
            context=self._context(),
        )
        assert not serializer.is_valid()
        assert "not found or not owned" in str(serializer.errors)
        assert Post.objects.count() == 0
        assert PostMedia.objects.count() == 0

    def test_rejects_missing_media_id(self):
        import uuid as uuid_mod

        fake = uuid_mod.uuid4()
        serializer = PostCreateSerializer(
            data={"content": "hi", "media_ids": [str(fake)]},
            context=self._context(),
        )
        assert not serializer.is_valid()
        assert "not found or not owned" in str(serializer.errors)

    def test_rejects_pending_media(self):
        media = _make_media(
            self.alice,
            s3_key="posts/x/pending.jpg",
            status=Media.UploadStatus.PENDING,
        )
        serializer = PostCreateSerializer(
            data={"content": "hi", "media_ids": [str(media.id)]},
            context=self._context(),
        )
        assert not serializer.is_valid()
        assert "COMPLETED" in str(serializer.errors)

    def test_rejects_failed_media(self):
        media = _make_media(
            self.alice,
            s3_key="posts/x/failed.jpg",
            status=Media.UploadStatus.FAILED,
        )
        serializer = PostCreateSerializer(
            data={"content": "hi", "media_ids": [str(media.id)]},
            context=self._context(),
        )
        assert not serializer.is_valid()
        assert "COMPLETED" in str(serializer.errors)

    def test_rejects_media_from_wrong_folder(self):
        # Avatar Media must never be accepted as post media, even though
        # the row is owned by the user and COMPLETED.
        media = _make_media(self.alice, s3_key="avatars/alice/me.jpg")
        serializer = PostCreateSerializer(
            data={"content": "hi", "media_ids": [str(media.id)]},
            context=self._context(),
        )
        assert not serializer.is_valid()
        assert "posts/ namespace" in str(serializer.errors)
        assert Post.objects.count() == 0
        assert PostMedia.objects.count() == 0


class TestPostUpdateSerializer(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", username="alice", password="TestPass123!"
        )
        self.post = Post.objects.create(author=self.alice, content="original")

    def test_update_sets_is_edited(self):
        serializer = PostUpdateSerializer(
            self.post, data={"content": "changed"}, partial=True
        )
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()

        assert updated.content == "changed"
        assert updated.is_edited is True
