"""Base models shared by every app."""

import uuid
from collections.abc import Iterable
from typing import Any, TypeVar, cast

from django.db import models
from django.db.models.base import ModelBase

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
