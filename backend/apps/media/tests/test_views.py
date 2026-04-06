from unittest.mock import MagicMock, patch

from botocore.exceptions import BotoCoreError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.media.models import Media


class TestPresignUploadView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.user = User.objects.create_user(email="testuser@example.com", username="testuser", password="TestPass123!")

        self.client.force_authenticate(user=self.user)

        self.valid_payload = {
            "file_name": "photo.jpg",
            "content_type": "image/jpeg",
            "file_size": 204800,
            "folder": "avatars",
        }

    @patch("apps.media.views.generate_presigned_upload_url")
    def test_returns_presigned_url_and_creates_media(self, mock_presign: MagicMock):
        mock_presign.return_value = {
            "upload_url": "https://s3.example.com/upload?sig=abc",
            "s3_key": "avatars/abc123/photo.jpg",
        }

        response = self.client.post("/api/media/presign/upload/", self.valid_payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "upload_url" in response.data
        assert "s3_key" in response.data
        assert "media_id" in response.data

        # verify s3 service was called
        mock_presign.assert_called_once_with(
            folder="avatars",
            filename="photo.jpg",
            content_type="image/jpeg",
            file_size=204800,
        )

        # verify a PENDING media record was created
        media = Media.objects.get(id=response.data["media_id"])
        assert media.upload_status == Media.UploadStatus.PENDING
        assert media.uploaded_by == self.user
        assert media.media_type == Media.MediaType.IMAGE
        assert media.s3_key == "avatars/abc123/photo.jpg"

    def test_requires_authentication(self):
        self.client.force_authenticate()

        response = self.client.post("/api/media/presign/upload/", self.valid_payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rejects_invalid_content_type(self):
        payload = {**self.valid_payload, "content_type": "application/octet-stream"}

        response = self.client.post("/api/media/presign/upload/", payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert Media.objects.count() == 0

    def test_rejects_oversized_image(self):
        payload = {**self.valid_payload, "file_size": 15 * 1024 * 1024}

        response = self.client.post("/api/media/presign/upload/", payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Media.objects.count() == 0

    @patch("apps.media.views.generate_presigned_upload_url")
    def test_video_upload_presign(self, mock_presign: MagicMock):
        mock_presign.return_value = {
            "upload_url": "https://s3.example.com/upload?sig=xyz",
            "s3_key": "posts/def456/clip.mp4",
        }

        payload = {
            "file_name": "clip.mp4",
            "content_type": "video/mp4",
            "file_size": 50 * 1024 * 1024,
            "folder": "posts",
        }

        response = self.client.post("/api/media/presign/upload/", payload, format="json")

        assert response.status_code == status.HTTP_200_OK

        media = Media.objects.get(id=response.data["media_id"])
        assert media.media_type == Media.MediaType.VIDEO
        assert media.upload_status == Media.UploadStatus.PENDING


class TestConfirmUploadView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.user = User.objects.create_user(
            email="testuser@example.com",
            username="testuser",
            password="TestPass1231",
        )
        self.client.force_authenticate(user=self.user)

        self.media = Media.objects.create(
            uploaded_by=self.user,
            s3_key="avatars/abc123/photo.jpg",
            media_type=Media.MediaType.IMAGE,
            content_type="image/jpeg",
            file_name="photo.jpg",
            upload_status=Media.UploadStatus.PENDING,
        )

    @patch("apps.media.views.verify_s3_object")
    def test_confirms_pending_upload(self, mock_verify: MagicMock):
        mock_verify.return_value = {
            "actual_size": 204800,
            "verified": True,
        }

        response = self.client.post(
            "/api/media/confirm-upload/",
            {"s3_key": "avatars/abc123/photo.jpg", "file_size": 204800},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        self.media.refresh_from_db()
        assert self.media.upload_status == Media.UploadStatus.COMPLETED
        assert self.media.file_size == 204800

    def test_returns_404_for_nonexistent_key(self):
        response = self.client.post(
            "/api/media/confirm-upload/",
            {"s3_key": "avatars/nonexistent/photo.jpg", "file_size": 1024},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_confirm_another_users_upload(self):
        other_user = User.objects.create_user(email="other@example.com", username="otheruser", password="TestPass123!")

        self.client.force_authenticate(user=other_user)

        response = self.client.post(
            "/api/media/confirm-upload/",
            {"s3_key": "avatars/abc123/photo.jpg", "file_size": 204800},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        self.media.refresh_from_db()
        assert self.media.upload_status == Media.UploadStatus.PENDING

    def test_cannot_confirm_already_completed_upload(self):
        self.media.upload_status = Media.UploadStatus.COMPLETED
        self.media.save()

        response = self.client.post(
            "/api/media/confirm-upload/",
            {"s3_key": "avatars/abc123/photo.jpg", "file_size": 204800},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_authentication(self):
        self.client.force_authenticate()

        response = self.client.post(
            "/api/media/confirm-upload/",
            {"s3_key": "avatars/abc123/photo.jpg", "file_size": 204800},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.media.views.delete_s3_object")
    @patch("apps.media.views.verify_s3_object")
    def test_rejects_size_mismatch(self, mock_verify: MagicMock, mock_delete: MagicMock):
        mock_verify.return_value = {"actual_size": 99999, "verified": False}

        response = self.client.post(
            "/api/media/confirm-upload/",
            {"s3_key": "avatars/abc123/photo.jpg", "file_size": 204800},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "File size mismatch" in response.data["detail"]
        assert response.data["actual_size"] == 99999

        # Orphaned s3 object should be deleted
        mock_delete.assert_called_once_with("avatars/abc123/photo.jpg")

        # media should be marked as failed
        self.media.refresh_from_db()
        assert self.media.upload_status == Media.UploadStatus.FAILED

    @patch("apps.media.views.verify_s3_object")
    def test_rejects_when_file_not_s3(self, mock_verify: MagicMock):
        mock_verify.side_effect = BotoCoreError()

        response = self.client.post(
            "/api/media/confirm-upload/",
            {"s3_key": "avatars/abc123/photo.jpg", "file_size": 204800},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not found in S3" in response.data["detail"]


class TestMediaDetailView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.user = User.objects.create_user(
            email="testuser@example.com",
            username="testuser",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.user)

        self.media = Media.objects.create(
            uploaded_by=self.user,
            s3_key="avatars/abc123/photo.jpg",
            media_type=Media.MediaType.IMAGE,
            content_type="image/jpeg",
            file_name="photo.jpg",
            file_size=204800,
            upload_status=Media.UploadStatus.COMPLETED,
        )

    @patch("apps.media.serializers.generate_presigned_read_url")
    def test_get_returns_media_with_presigned_url(self, mock_read_url: MagicMock):
        mock_read_url.return_value = "https://s3.example.com/photo.jpg?sig=abc"

        response = self.client.get(f"/api/media/{self.media.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(self.media.id)
        assert response.data["url"] == "https://s3.example.com/photo.jpg?sig=abc"
        assert response.data["media_type"] == "image"
        assert response.data["file_name"] == "photo.jpg"

    @patch("apps.media.serializers.generate_presigned_read_url")
    def test_pending_media_returns_null_url(self, mock_read_url: MagicMock):
        self.media.upload_status = Media.UploadStatus.PENDING
        self.media.save()

        response = self.client.get(f"/api/media/{self.media.id}/")
        assert response.data["url"] is None

        mock_read_url.assert_not_called()

    def test_cannot_access_another_users_media(self):
        other_user = User.objects.create_user(email="other@example.com", username="otheruser", password="TestPass123!")

        self.client.force_authenticate(user=other_user)

        response = self.client.get(f"/api/media/{self.media.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.media.views.delete_s3_object")
    def test_delete_removes_from_s3_and_db(self, mock_delete: MagicMock):
        media_id = self.media.id
        s3_key = self.media.s3_key

        response = self.client.delete(f"/api/media/{media_id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Media.objects.filter(id=media_id).exists()
        mock_delete.assert_called_once_with(s3_key)

    @patch("apps.media.views.delete_s3_object")
    def test_cannot_delete_another_users_media(self, mock_delete: MagicMock):
        other_user = User.objects.create_user(email="other@example.com", username="otheruser", password="TestPass123!")

        self.client.force_authenticate(user=other_user)

        response = self.client.delete(f"/api/media/{self.media.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_delete.assert_not_called()
        assert Media.objects.filter(id=self.media.id).exists()

    def test_requires_authentication(self):
        self.client.force_authenticate()

        response = self.client.get(f"/api/media/{self.media.id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
