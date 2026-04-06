from django.test import TestCase

from apps.media.models import Media
from apps.media.serializers import ConfirmUploadSerializer, PresignUploadSerializer


class TestPresignUploadSerializer(TestCase):
    def test_valid_image_upload(self):
        data = {
            "file_name": "photo.jpg",
            "content_type": "image/jpeg",
            "file_size": 2 * 1024 * 1024,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["media_type"] == Media.MediaType.IMAGE

    def test_valid_video_upload(self):
        data = {
            "file_name": "clip.mp4",
            "content_type": "video/mp4",
            "file_size": 50 * 1024 * 1024,
            "folder": "posts",
        }

        serializer = PresignUploadSerializer(data=data)

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["media_type"] == Media.MediaType.VIDEO

    def test_all_allowed_image_types(self):
        for content_type in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
            data = {
                "file_name": "test.img",
                "content_type": content_type,
                "file_size": 2 * 1024 * 1024,
                "folder": "avatars",
            }

            serializer = PresignUploadSerializer(data=data)

            assert serializer.is_valid(), f"{content_type} should be allowed: {serializer.errors}"

    def test_all_allowed_video_types(self):
        for content_type in ["video/mp4", "video/webm", "video/quicktime"]:
            data = {
                "file_name": "test.vid",
                "content_type": content_type,
                "file_size": 2 * 1024 * 1024,
                "folder": "posts",
            }

            serializer = PresignUploadSerializer(data=data)

            assert serializer.is_valid(), f"{content_type} should be allowed: {serializer.errors}"

    def test_rejects_unsupported_content_type(self):
        data = {
            "file_name": "malware.exe",
            "content_type": "application/octet-stream",
            "file_size": 1024,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "content_type" in serializer.errors

    def test_rejects_pdf(self):
        data = {
            "file_name": "document.pdf",
            "content_type": "application/pdf",
            "file_size": 1024,
            "folder": "posts",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "content_type" in serializer.errors

    def test_rejects_text_file(self):
        data = {
            "file_name": "notes.txt",
            "content_type": "text/plain",
            "file_size": 1024,
            "folder": "posts",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()

    def tests_rejects_oversized_image(self):
        data = {
            "file_name": "huge.jpg",
            "content_type": "image/jpeg",
            "file_size": 15 * 1024 * 1024,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "file_size" in serializer.errors

    def test_rejects_oversized_video(self):
        data = {
            "file_name": "huge.mp4",
            "content_type": "video/mp4",
            "file_size": 150 * 1024 * 1024,
            "folder": "posts",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "file_size" in serializer.errors

    def tests_image_at_exact_limit_passes(self):
        data = {
            "file_name": "exact.jpg",
            "content_type": "image/jpeg",
            "file_size": 10 * 1024 * 1024,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert serializer.is_valid(), serializer.errors

    def test_rejects_zero_file_size(self):
        data = {
            "file_name": "empty.jpg",
            "content_type": "image/jpeg",
            "file_size": 0,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()

    def test_rejects_negative_file_size(self):
        data = {
            "file_name": "negative.jpg",
            "content_type": "image/jpeg",
            "file_size": -100,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()

    def test_rejects_invalid_folder(self):
        data = {
            "file_name": "photo.jpg",
            "content_type": "image/jpeg",
            "file_size": 1024,
            "folder": "not_valid",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "folder" in serializer.errors

    def test_avatars_folder_allowed(self):
        data = {
            "file_name": "a.jpg",
            "content_type": "image/jpeg",
            "file_size": 1024,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert serializer.is_valid()

    def test_posts_folder_allowed(self):
        data = {
            "file_name": "a.jpg",
            "content_type": "image/jpeg",
            "file_size": 1024,
            "folder": "posts",
        }

        serializer = PresignUploadSerializer(data=data)

        assert serializer.is_valid()

    def test_rejects_missing_file_name(self):
        data = {
            "content_type": "image/jpeg",
            "file_size": 1024,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "file_name" in serializer.errors

    def test_rejects_missing_content_type(self):
        data = {
            "file_name": "a.jpg",
            "file_size": 1024,
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "content_type" in serializer.errors

    def test_rejects_file_size(self):
        data = {
            "file_name": "a.jpg",
            "content_type": "image/jpeg",
            "folder": "avatars",
        }

        serializer = PresignUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "file_size" in serializer.errors

    def test_rejects_empty_body(self):
        serializer = PresignUploadSerializer(data={})

        assert not serializer.is_valid()


class TestConfirmUploadSerializer(TestCase):
    def test_valid_data(self):
        data = {"s3_key": "avatars/abc123/photo.jpg", "file_size": 204800}
        serializer = ConfirmUploadSerializer(data=data)

        assert serializer.is_valid()

    def test_rejects_missing_s3_key(self):
        data = {"file_size": 204800}
        serializer = ConfirmUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "s3_key" in serializer.errors

    def test_rejects_missing_file_size(self):
        data = {"s3_key": "avatars/abc123/photo.jpg"}
        serializer = ConfirmUploadSerializer(data=data)

        assert not serializer.is_valid()
        assert "file_size" in serializer.errors

    def test_rejects_zero_file_size(self):
        data = {"s3_key": "avatars/abc123/photo.jpg", "file_size": 0}
        serializer = ConfirmUploadSerializer(data=data)

        assert not serializer.is_valid()
