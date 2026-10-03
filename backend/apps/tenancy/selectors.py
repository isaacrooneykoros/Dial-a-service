"""Read queries for the tenancy app. Other apps call these, never the models directly."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.core.cache import cache

from apps.tenancy.models import Business, BusinessBranding, BusinessDomain, BusinessSetting
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


def decimal_setting(key: str) -> Decimal:
    """A percentage setting (stored as a decimal string) as an exact Decimal."""
    value = get_setting(key)
    if not isinstance(value, str):
        raise TypeError(f"Setting {key!r} is not stored as a decimal string.")
    return Decimal(value)


def business_currency(business_id: UUID) -> str:
    """The currency a business charges in (KES for every business today)."""
    currency = Business.objects.filter(pk=business_id).values_list("currency", flat=True).first()
    if currency is None:
        raise LookupError(f"Business {business_id} doesn't exist.")
    return str(currency)


def all_business_ids() -> list[UUID]:
    """Every business ID, for platform jobs that work business by business."""
    return list(Business.objects.order_by("created_at").values_list("id", flat=True))


def support_contact(business_id: UUID) -> tuple[str, str]:
    """The name customers and staff know the business by, and its support phone (E.164 or "")."""
    branding = BusinessBranding.objects.values_list("app_name", "support_phone").first()
    if branding is not None and branding[0]:
        return branding[0], branding[1]
    name = Business.objects.filter(pk=business_id).values_list("name", flat=True).first()
    return name or "", ""


def primary_host(business_id: UUID) -> str:
    """The business's main web address, for links in messages."""
    host = (
        BusinessDomain.objects.filter(business_id=business_id)
        .order_by("-is_primary", "created_at")
        .values_list("host", flat=True)
        .first()
    )
    if host is None:
        raise LookupError(f"Business {business_id} has no web address.")
    return str(host)


def business_config(business_id: UUID) -> dict[str, Any]:
    """What every app needs at start-up (X-01). Never anything secret."""
    business = Business.objects.get(pk=business_id)
    branding = BusinessBranding.objects.first()
    defaults = BusinessBranding()
    return {
        "business": {
            "name": business.name,
            "slug": business.slug,
            "country": business.country,
            "currency": business.currency,
            "timezone": business.timezone,
            "language": business.language,
        },
        "branding": {
            "app_name": branding.app_name if branding else business.name,
            "logo_url": branding.logo_url if branding else "",
            "primary_color": (branding or defaults).primary_color,
            "accent_color": (branding or defaults).accent_color,
            "support_phone": branding.support_phone if branding else "",
            "whatsapp_phone": branding.whatsapp_phone if branding else "",
            "terms_url": branding.terms_url if branding else "",
            "privacy_url": branding.privacy_url if branding else "",
        },
    }
