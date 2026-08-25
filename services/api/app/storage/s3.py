from __future__ import annotations

from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class S3Storage:
    def __init__(self) -> None:
        # Internal client:
        # Used by the API/worker containers to communicate with MinIO.
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

        # Public client:
        # Used only to generate presigned URLs that are consumed by
        # the user's browser. The browser cannot resolve the Docker
        # hostname "minio", so these URLs must use localhost.
        self.presign_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_public_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def create_presigned_put_url(
        self,
        *,
        object_key: str,
        content_type: str,
    ) -> str:
        return self.presign_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=settings.s3_presigned_url_expire_seconds,
            HttpMethod="PUT",
        )

    def create_presigned_get_url(
        self,
        *,
        object_key: str,
    ) -> str:
        return self.presign_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": object_key,
            },
            ExpiresIn=settings.s3_presigned_url_expire_seconds,
            HttpMethod="GET",
        )

    def head_object(
        self,
        *,
        object_key: str,
    ) -> dict:
        return self.client.head_object(
            Bucket=settings.s3_bucket,
            Key=object_key,
        )

    def download_object(
        self,
        *,
        object_key: str,
    ) -> bytes:
        response = self.client.get_object(
            Bucket=settings.s3_bucket,
            Key=object_key,
        )

        body = response["Body"]

        try:
            return body.read()
        finally:
            body.close()

    def upload_fileobj(
        self,
        *,
        fileobj: BinaryIO,
        object_key: str,
        content_type: str,
    ) -> None:
        self.client.upload_fileobj(
            fileobj,
            settings.s3_bucket,
            object_key,
            ExtraArgs={
                "ContentType": content_type,
            },
        )

    def delete_object(
        self,
        *,
        object_key: str,
    ) -> None:
        try:
            self.client.delete_object(
                Bucket=settings.s3_bucket,
                Key=object_key,
            )
        except ClientError:
            pass


_storage = S3Storage()


def get_storage() -> S3Storage:
    return _storage
