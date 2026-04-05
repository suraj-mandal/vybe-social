"""
Setup script to create S3 bucket in MinIO
"""

import boto3
from botocore.exceptions import ClientError

# These must match your MinIO .env values
ENDPOINT_URL = "http://minio:9000"
ACCESS_KEY = "vybe_minio_admin"
SECRET_KEY = "vybe_minio_secret"
BUCKET_NAME = "vybe-media"
REGION = "us-east-1"


def create_bucket() -> None:
    """
    Creates an S3 bucket if it does not already exist.

    This function connects to an Amazon S3-compatible service using provided credentials
    and checks if a bucket with the given name exists. If the bucket does not exist,
    it creates the bucket. The S3 client configuration includes an endpoint URL,
    access key, secret access key, and region.

    :raises ClientError: If the S3 service responds with an error while trying to
                         access or create the bucket.
    :return: None
    """
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
    )

    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' already exists.")
    except ClientError:
        s3.create_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' created successfully.")


if __name__ == "__main__":
    create_bucket()
