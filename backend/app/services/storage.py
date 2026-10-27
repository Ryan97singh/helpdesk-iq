"""Object storage: S3 (or MinIO locally via docker-compose) when configured, local disk otherwise."""

import uuid
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


class Storage(ABC):
    @abstractmethod
    def put(self, filename: str, data: bytes) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


def _key(filename: str) -> str:
    safe = "".join(ch for ch in Path(filename).name if ch.isalnum() or ch in "._-") or "file"
    return f"documents/{uuid.uuid4().hex}-{safe}"


class LocalStorage(Storage):
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):  # path traversal guard
            raise ValueError("invalid storage key")
        return path

    def put(self, filename: str, data: bytes) -> str:
        key = _key(filename)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage(Storage):
    def __init__(self, bucket: str, endpoint_url: str | None) -> None:
        import boto3

        self.bucket = bucket
        self.s3 = boto3.client("s3", endpoint_url=endpoint_url)  # credentials from IAM role / env

    def put(self, filename: str, data: bytes) -> str:
        key = _key(filename)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")
        return key

    def get(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    return S3Storage(s.s3_bucket, s.s3_endpoint_url) if s.s3_bucket else LocalStorage(s.storage_dir)
