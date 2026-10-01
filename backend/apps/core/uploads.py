"""Starting and confirming uploads (ADR-0004). Business logic for /uploads lives here."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.core import audit
from apps.core.models import Upload
from apps.core.storage import UPLOAD_URL_LIFETIME, get_storage
from apps.core.tenant_context import get_current_business_id

EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class UploadError(Exception):
    def __init__(self, code: str, field: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.field = field


@dataclass(frozen=True)
class UploadTicket:
    upload: Upload
    url: str
    expires_at: datetime


def check_limits(content_type: str, size: int) -> None:
    if content_type not in settings.UPLOAD_CONTENT_TYPES:
        raise UploadError("unsupported_type", "content_type")
    if size <= 0 or size > settings.UPLOAD_MAX_BYTES:
        raise UploadError("too_large", "size")


def start_upload(*, content_type: str, size: int, user: Any = None) -> UploadTicket:
    check_limits(content_type, size)
    business_id = get_current_business_id()
    upload_id = uuid.uuid4()
    key = f"{business_id}/uploads/{upload_id}.{EXTENSIONS[content_type]}"
    upload = Upload.objects.create(
        id=upload_id, key=key, content_type=content_type, size=size, uploaded_by=user
    )
    url = get_storage().upload_url(
        key=key, content_type=content_type, upload_id=str(upload_id), business_id=str(business_id)
    )
    return UploadTicket(upload=upload, url=url, expires_at=timezone.now() + UPLOAD_URL_LIFETIME)


def complete_upload(upload: Upload, *, user: Any = None, request: Any = None) -> Upload:
    """Confirm the file arrived as declared; only then can other records use it."""
    if upload.status == Upload.Status.UPLOADED:
        return upload
    stored = get_storage().stat(upload.key)
    if stored is None:
        raise UploadError("not_uploaded")
    if stored.size != upload.size or stored.content_type != upload.content_type:
        raise UploadError("does_not_match")
    upload.status = Upload.Status.UPLOADED
    upload.save(update_fields=["status", "updated_at"])
    audit.record("upload.complete", obj=upload, actor=user, request=request)
    return upload
