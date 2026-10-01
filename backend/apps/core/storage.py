"""Private file storage for uploads (ADR-0004).

Two adapters behind one interface, chosen by STORAGE_BACKEND:
- "r2": Cloudflare R2 (S3 API) via boto3 - presigned PUT URLs, HEAD to confirm.
- "local": a signed, expiring Django endpoint writing to MEDIA_PRIVATE_ROOT.
"""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing

UPLOAD_URL_LIFETIME = timedelta(minutes=5)
LOCAL_SIGNING_SALT = "dial-a-service.local-upload"


@dataclass(frozen=True)
class StoredObject:
    size: int
    content_type: str


class Storage(Protocol):
    def upload_url(self, *, key: str, content_type: str, upload_id: str, business_id: str) -> str:
        """A URL the client can PUT the file to for the next 5 minutes."""
        ...

    def stat(self, key: str) -> StoredObject | None:
        """The stored object's size and type, or None if it isn't there."""
        ...


class R2Storage:
    def __init__(self) -> None:
        import boto3

        self.bucket = settings.STORAGE_BUCKET
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
            region_name="auto",
        )

    def upload_url(self, *, key: str, content_type: str, upload_id: str, business_id: str) -> str:
        url: str = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=int(UPLOAD_URL_LIFETIME.total_seconds()),
        )
        return url

    def stat(self, key: str) -> StoredObject | None:
        from botocore.exceptions import ClientError

        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return None
        return StoredObject(size=int(head["ContentLength"]), content_type=head["ContentType"])


class LocalStorage:
    """Development and tests: files under MEDIA_PRIVATE_ROOT, uploaded through Django."""

    def root(self) -> Path:
        return Path(settings.MEDIA_PRIVATE_ROOT)

    def path_for(self, key: str) -> Path:
        path = (self.root() / key).resolve()
        if self.root().resolve() not in path.parents:
            raise ValueError("Upload key escapes the storage folder.")
        return path

    def upload_url(self, *, key: str, content_type: str, upload_id: str, business_id: str) -> str:
        token = signing.dumps(
            {"upload": upload_id, "business": business_id}, salt=LOCAL_SIGNING_SALT
        )
        return f"/api/v1/uploads/{upload_id}/content?{urlencode({'token': token})}"

    def read_token(self, token: str) -> dict[str, str] | None:
        try:
            data: dict[str, str] = signing.loads(
                token,
                salt=LOCAL_SIGNING_SALT,
                max_age=int(UPLOAD_URL_LIFETIME.total_seconds()),
            )
        except signing.BadSignature:
            return None
        return data

    def save(self, key: str, content: bytes, content_type: str) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.with_suffix(path.suffix + ".type").write_text(content_type, encoding="utf-8")

    def stat(self, key: str) -> StoredObject | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        type_file = path.with_suffix(path.suffix + ".type")
        content_type = type_file.read_text(encoding="utf-8") if type_file.exists() else ""
        return StoredObject(size=path.stat().st_size, content_type=content_type)


def get_storage() -> Storage:
    if settings.STORAGE_BACKEND == "r2":
        return R2Storage()
    return LocalStorage()
