"""Base models shared by every app."""

import uuid
from collections.abc import Iterable
from typing import Any, ClassVar, TypeVar, cast

from django.conf import settings
from django.db import models
from django.db.models.base import ModelBase
from django.utils import timezone

from apps.core.tenant_context import TenantMismatch, get_current_business_id

_M = TypeVar("_M", bound="TenantModel")


class BaseModel(models.Model):
    """UUID primary key and UTC timestamps (design doc "Data model").

    IDs are random UUIDs so they can be exposed through the API without
    revealing counts or ordering.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantManager(models.Manager[_M]):
    """Layer 1 of tenant isolation (ADR-0001 section 3).

    Every query is filtered to the business in context, and running one with no
    business in context raises TenantContextMissing instead of returning every
    business's rows.
    """

    def get_queryset(self) -> models.QuerySet[_M]:
        return super().get_queryset().filter(business_id=get_current_business_id())

    def bulk_create(self, objs: Iterable[_M], *args: Any, **kwargs: Any) -> list[_M]:
        # bulk_create skips save(), so apply the same guard here.
        objs = list(objs)
        for obj in objs:
            obj.assign_current_business()
        return super().bulk_create(objs, *args, **kwargs)


class TenantModel(BaseModel):
    """Base for every business-owned model (CLAUDE.md section 6.1).

    - ``business`` is required, indexed, not editable (never read from client
      data) and has no reverse accessor, so ``business.<rows>`` can't bypass
      the manager.
    - ``objects`` is scoped to the current business.
    - ``unscoped`` is for platform code only; every use carries a
      ``# platform-scope: <reason>`` comment on the same line (checked by
      tests/test_code_rules.py).
    - Every table also gets row-level security through EnableTenantRLS.
    """

    business = models.ForeignKey(
        "tenancy.Business",
        on_delete=models.PROTECT,
        editable=False,
        db_index=True,
        related_name="+",
    )

    objects: TenantManager[Any] = TenantManager()
    unscoped: models.Manager[Any] = models.Manager()

    class Meta:
        abstract = True
        default_manager_name = "objects"
        base_manager_name = "unscoped"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        self.assign_current_business()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def assign_current_business(self) -> None:
        """Fill ``business`` from the context, or refuse a different business.

        An integrity guard, not business logic (ADR-0001 section 3).
        """
        current = get_current_business_id()
        # The type hints say business_id is always set; before the first save it isn't.
        assigned = cast("uuid.UUID | None", self.business_id)
        if assigned is None:
            self.business_id = current
        elif assigned != current:
            raise TenantMismatch(
                f"{type(self).__name__} belongs to business {self.business_id}, "
                f"but the current business is {current}."
            )


class AuditLogManager(models.Manager["AuditLog"]):
    """Scoped to the current business (raises without one), like TenantManager."""

    def get_queryset(self) -> models.QuerySet["AuditLog"]:
        return super().get_queryset().filter(business_id=get_current_business_id())


class AuditLog(models.Model):
    """Who did what, when and from where (CLAUDE.md section 6.7; A-63, P-12).

    Append-only: the app roles can't UPDATE or DELETE it (MakeAppendOnly).
    Nullable business: platform actions (P-12) belong to no business and are
    written by the platform service. Write with apps.core.audit.record().
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "tenancy.Business",
        on_delete=models.PROTECT,
        null=True,
        editable=False,
        db_index=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    # The registered counter device (accounts.Device, T06), kept as a plain ID
    # so core doesn't depend on accounts.
    device_id = models.UUIDField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    objects: ClassVar[AuditLogManager] = AuditLogManager()
    unscoped: ClassVar[models.Manager["AuditLog"]] = models.Manager()

    class Meta:
        default_manager_name = "objects"
        base_manager_name = "unscoped"
        indexes = [
            models.Index(fields=["business", "created_at"], name="auditlog_business_time"),
            models.Index(fields=["business", "object_type", "object_id"], name="auditlog_object"),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}:{self.object_id}"


class OutboxEvent(TenantModel):
    """A side effect to perform after the transaction commits (CLAUDE.md section 6.4).

    Written in the same transaction as the change it belongs to, so it exists
    if and only if the change committed. The worker dispatches it to the
    handler registered for its type (apps.core.outbox), retrying with backoff.
    """

    type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    available_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    processed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["business", "available_at"],
                condition=models.Q(processed_at__isnull=True, failed_at__isnull=True),
                name="outbox_pending",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type} ({self.pk})"


class IdempotencyKey(TenantModel):
    """A request the apps may retry; the first response is kept for 24 hours (CLAUDE.md 6.5).

    ``scope`` is the signed-in user's ID, or "ip:<address>" for anonymous calls.
    A row without a stored response is a request still in progress.
    """

    scope = models.CharField(max_length=80)
    key = models.CharField(max_length=100)
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=255)
    body_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    response_content_type = models.CharField(max_length=100, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "scope", "key"], name="idempotency_key_unique"
            ),
        ]
        indexes = [models.Index(fields=["business", "expires_at"], name="idempotency_expiry")]

    def __str__(self) -> str:
        return f"{self.method} {self.path} ({self.key})"


class AppVersion(BaseModel):
    """Minimum and latest version per app and platform (X-01, X-02). Global."""

    app = models.CharField(max_length=20)
    platform = models.CharField(max_length=20)
    minimum = models.CharField(max_length=20)
    latest = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["app", "platform"], name="one_version_per_app"),
        ]

    def __str__(self) -> str:
        return f"{self.app}/{self.platform} {self.minimum}..{self.latest}"


class Upload(TenantModel):
    """A private file uploaded straight to storage (ADR-0004). Others refer to it by ID."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UPLOADED = "uploaded", "Uploaded"

    key = models.CharField(max_length=255, unique=True, editable=False)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    def __str__(self) -> str:
        return self.key
