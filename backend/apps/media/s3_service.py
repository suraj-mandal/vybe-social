import uuid
from typing import Any

import boto3
from django.conf import settings
from types_boto3_s3.client import S3Client


def _get_s3_client() -> S3Client:
    """
    Initializes and returns an S3 client object. The client is configured using
    AWS credentials and parameters defined in the application's settings. If an
    S3 endpoint URL is specified in the settings, it is included in the client
    configuration.

    :return: An instance of S3Client initialized with the provided configurations.
    :rtype: S3Client
    """
    kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_S3_REGION_NAME,
    }

    if settings.AWS_S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL

    return boto3.client("s3", **kwargs)


def _to_external_url(presigned_url: str) -> str:
    """
    Converts an internal S3 presigned URL into an external S3 URL if the internal and
    external endpoint URLs are defined in the settings. If either of the URLs is not
    defined, the original presigned URL is returned unchanged.

    :param presigned_url: The S3 presigned URL to be converted.
    :type presigned_url: str
    :return: The converted external S3 URL if both internal and external URLs are
        configured; otherwise, the original presigned URL.
    :rtype: str
    """
    internal = settings.AWS_S3_ENDPOINT_URL
    external = settings.AWS_S3_EXTERNAL_URL

    if not internal or not external:
        return presigned_url

    return presigned_url.replace(internal, external)


def generate_presigned_upload_url(folder: str, filename: str, content_type: str, file_size: int) -> dict[str, str]:
    """
    Generates a presigned URL for uploading a file to S3. This function constructs
    a unique S3 object key based on the provided folder, filename, and a generated
    UUID. It then creates a presigned URL allowing the file to be uploaded to the
    specified S3 bucket with the given content type and file size.

    :param folder: The target folder path within the S3 bucket for storing the file.
                   This acts as a base directory for the upload.
    :type folder: str

    :param filename: The name of the file to be uploaded. If no extension is present
                     in the name, the generated S3 key will exclude an extension.
    :type filename: str

    :param content_type: The MIME type of the file, required for enforcing correct
                         file type during the upload process.
    :type content_type: str

    :param file_size: The size of the file (in bytes) to validate the upload request.
    :type file_size: int

    :return: A dictionary containing the presigned upload URL and the S3 object
             key associated with the file.
    :rtype: dict[str, str]
    """
    s3 = _get_s3_client()

    extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
    unique_id = uuid.uuid4().hex
    s3_key = f"{folder}/{unique_id}/{filename}" if extension else f"{folder}/{unique_id}"

    presigned_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": content_type,
            "ContentLength": file_size,
        },
        ExpiresIn=settings.AWS_PRESIGNED_URL_EXPIRY,
    )

    return {"upload_url": _to_external_url(presigned_url), "s3_key": s3_key}


def generate_presigned_read_url(s3_key: str) -> str:
    """
    Generates a presigned URL for reading an object from an S3 bucket. This URL can be
    used to access the object externally for a limited period of time, as configured
    by the expiry settings.

    :param s3_key: The key of the object in the S3 bucket to generate a presigned URL for.
    :type s3_key: str
    :return: The generated presigned URL for reading the object.
    :rtype: str
    """
    s3 = _get_s3_client()

    presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": s3_key,
        },
        ExpiresIn=settings.AWS_PRESIGNED_URL_EXPIRY,
    )

    return _to_external_url(presigned_url)


def delete_s3_object(s3_key: str) -> None:
    """
    Delete an object from an S3 bucket.

    This function interacts with the Amazon S3 service to delete a specific object from a given bucket.
    The object to delete is identified by the provided S3 key.

    :param s3_key: The unique key identifying the object in the S3 bucket.
    :type s3_key: str
    :return: None
    """
    s3 = _get_s3_client()

    s3.delete_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=s3_key,
    )


def verify_s3_object(s3_key: str, expected_size: int) -> dict[str, Any]:
    s3 = _get_s3_client()

    response = s3.head_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=s3_key,
    )

    actual_size = response["ContentLength"]

    return {"actual_size": actual_size, "verified": actual_size == expected_size}
