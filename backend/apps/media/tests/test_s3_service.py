from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.media.s3_service import (
    _to_external_url,
    delete_s3_object,
    generate_presigned_read_url,
    generate_presigned_upload_url,
    verify_s3_object,
)


class TestToExternalUrl(TestCase):
    @override_settings(
        AWS_S3_ENDPOINT_URL="http://minio:9000",
        AWS_S3_EXTERNAL_URL="http://localhost:9000",
    )
    def test_replaces_internal_with_external_url(self):
        internal = "http://minio:9000/vybe-media/avatars/photo.jpg?sig=abc"
        result = _to_external_url(internal)

        assert (
            result
            == "http://localhost:9000/vybe-media/avatars/photo.jpg?sig=abc"
        )

    @override_settings(AWS_S3_ENDPOINT_URL="", AWS_S3_EXTERNAL_URL="")
    def test_noop_when_urls_are_empty(self):
        url = "https://vybe-media.s3.amazonaws.com/avatars/photo.jpg?sig=abc"
        result = _to_external_url(url)

        assert result == url

    @override_settings(
        AWS_S3_ENDPOINT_URL="http://minio:9000", AWS_S3_EXTERNAL_URL=""
    )
    def test_noop_when_external_is_empty(self):
        url = "http://minio:9000/vybe-media/photo.jpg?sig=abc"
        result = _to_external_url(url)

        assert result == url


class TestGeneratePresignedUploadUrl(TestCase):
    @patch("apps.media.s3_service._get_s3_client")
    @override_settings(
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_PRESIGNED_URL_EXPIRY=3600,
        AWS_S3_EXTERNAL_URL="",
        AWS_S3_ENDPOINT_URL="",
    )
    def test_generates_upload_url_with_correct_params(
        self, mock_get_client: MagicMock
    ):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = (
            "https://s3.example.com/signed-url"
        )
        mock_get_client.return_value = mock_s3

        result = generate_presigned_upload_url(
            folder="avatars",
            filename="photo.jpg",
            content_type="image/jpeg",
            file_size=204800,
        )

        assert "upload_url" in result
        assert "s3_key" in result
        assert result["upload_url"] == "https://s3.example.com/signed-url"

        # verify boto3 called
        call_kwargs = mock_s3.generate_presigned_url.call_args
        assert call_kwargs.kwargs["ClientMethod"] == "put_object"
        assert call_kwargs.kwargs["Params"]["Bucket"] == "test-bucket"
        assert call_kwargs.kwargs["Params"]["ContentType"] == "image/jpeg"
        assert call_kwargs.kwargs["Params"]["ContentLength"] == 204800
        assert call_kwargs.kwargs["ExpiresIn"] == 3600

    @patch("apps.media.s3_service._get_s3_client")
    @override_settings(
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_PRESIGNED_URL_EXPIRY=3600,
        AWS_S3_EXTERNAL_URL="",
        AWS_S3_ENDPOINT_URL="",
    )
    def test_generates_unique_s3_keys(self, mock_get_client: MagicMock):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = (
            "https://s3.example.com/signed"
        )
        mock_get_client.return_value = mock_s3

        result1 = generate_presigned_upload_url(
            "avatars", "photo.jpg", "image/jpeg", 1024
        )
        result2 = generate_presigned_upload_url(
            "avatars", "photo.jpg", "image/jpeg", 1024
        )

        assert result1["s3_key"] != result2["s3_key"]


class TestGeneratePresignedReadUrl(TestCase):
    @patch("apps.media.s3_service._get_s3_client")
    @override_settings(
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_PRESIGNED_URL_EXPIRY=3600,
        AWS_S3_ENDPOINT_URL="",
        AWS_S3_EXTERNAL_URL="",
    )
    def test_generates_read_url(self, mock_get_client: MagicMock):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = (
            "https://s3.example.com/read-url"
        )
        mock_get_client.return_value = mock_s3

        result = generate_presigned_read_url("avatars/abc123/photo.jpg")

        assert result == "https://s3.example.com/read-url"

        call_kwargs = mock_s3.generate_presigned_url.call_args
        assert call_kwargs.kwargs["ClientMethod"] == "get_object"
        assert call_kwargs.kwargs["Params"]["Bucket"] == "test-bucket"
        assert call_kwargs.kwargs["Params"]["Key"] == "avatars/abc123/photo.jpg"


class TestDeleteS3Object(TestCase):
    @patch("apps.media.s3_service._get_s3_client")
    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_deletes_object(self, mock_get_client: MagicMock):
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        delete_s3_object("avatars/abc123/photo.jpg")

        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="avatars/abc123/photo.jpg"
        )


class TestVerifyS3Object(TestCase):
    @patch("apps.media.s3_service._get_s3_client")
    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_verified_when_size_matches(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 204800}
        mock_get_client.return_value = mock_s3

        result = verify_s3_object("avatars/abc123/photo.jpg", 204800)

        assert result["verified"] is True
        assert result["actual_size"] == 204800

        mock_s3.head_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="avatars/abc123/photo.jpg",
        )

    @patch("apps.media.s3_service._get_s3_client")
    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_not_verified_when_size_differs(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 999999}
        mock_get_client.return_value = mock_s3

        result = verify_s3_object("avatars/abc123/photo.jpg", 204800)

        assert result["verified"] is False
        assert result["actual_size"] == 999999

    @patch("apps.media.s3_service._get_s3_client")
    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_raises_when_object_not_found(self, mock_get_client):
        """If the object doesn't exist, head_object raises a ClientError."""
        from botocore.exceptions import ClientError

        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )
        mock_get_client.return_value = mock_s3

        with self.assertRaises(ClientError):
            verify_s3_object("avatars/nonexistent/photo.jpg", 204800)
