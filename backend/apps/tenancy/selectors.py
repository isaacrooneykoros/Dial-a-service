"""Read queries for the tenancy app. Other apps call these, never the models directly."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.core.cache import cache

from apps.tenancy.models import Business, BusinessDomain, BusinessSetting
from apps.tenancy.settings_registry import get_spec

HOST_CACHE_SECONDS = 60  # CLAUDE.md section 6.1
_NOT_FOUND = "-"  # cached marker for unknown hosts


@dataclass(frozen=True)
class ResolvedBusiness:
    """What a request needs to know about its business. Small enough to cache."""

    id: UUID
    slug: str
    status: str


def _host_cache_key(host: str) -> str:
    return f"tenancy:host:{host}"


def resolve_host(host: str) -> ResolvedBusiness | None:
    """The business served at ``host`` (already normalised), cached for 60 seconds.

    Unknown hosts are cached too, so random hosts can't hammer the database.
    """
    key = _host_cache_key(host)
    cached = cache.get(key)
    if cached == _NOT_FOUND:
        return None
    if isinstance(cached, ResolvedBusiness):
        return cached

    row = (
        BusinessDomain.objects.filter(host=host)
        .values_list("business_id", "business__slug", "business__status")
        .first()
    )
    resolved = ResolvedBusiness(id=row[0], slug=row[1], status=row[2]) if row else None
    cache.set(key, resolved or _NOT_FOUND, HOST_CACHE_SECONDS)
    return resolved


def forget_host(host: str) -> None:
    """Drop a cached lookup, for code that changes a business's domains."""
    cache.delete(_host_cache_key(host))


def get_setting(key: str) -> Any:
    """The current business's value for a declared setting, or its default."""
    spec = get_spec(key)
    row = BusinessSetting.objects.filter(key=key).values_list("value", flat=True).first()
    return spec.default if row is None else row


def all_business_ids() -> list[UUID]:
    """Every business ID, for platform jobs that work business by business."""
    return list(Business.objects.order_by("created_at").values_list("id", flat=True))
