"""Read queries for the catalogue (M2 T04). Other apps call these, never the models.

A price is valid from ``effective_from`` up to, not including, ``effective_to``. At
a branch, the branch's own override wins; otherwise the business-wide price applies.
"""

from datetime import datetime
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.catalog.models import PriceModifier, PriceModifierService, Service, ServicePrice
from apps.catalog.pricing import ModifierSnapshot, PriceSnapshot


def _valid_at(at: datetime) -> Q:
    return Q(effective_from__lte=at) & (Q(effective_to__isnull=True) | Q(effective_to__gt=at))


def price_at(
    service_id: Any, *, branch_id: Any = None, at: datetime | None = None
) -> ServicePrice | None:
    """The price version that applies to a service at a moment (now by default)."""
    moment = at or timezone.now()
    valid = ServicePrice.objects.filter(_valid_at(moment), service_id=service_id)
    if branch_id is not None:
        override: ServicePrice | None = valid.filter(branch_id=branch_id).first()
        if override is not None:
            return override
    business_wide: ServicePrice | None = valid.filter(branch__isnull=True).first()
    return business_wide


def price_versions(service_id: Any, *, branch_id: Any = None) -> QuerySet[ServicePrice]:
    """Every version for a service, newest first: business-wide, or one branch's overrides."""
    versions = ServicePrice.objects.filter(service_id=service_id)
    if branch_id is None:
        return versions.filter(branch__isnull=True).order_by("-effective_from")
    return versions.filter(branch_id=branch_id).order_by("-effective_from")


def has_prices(service_id: Any) -> bool:
    return ServicePrice.objects.filter(service_id=service_id).exists()


def service_by_code(code: str) -> Service | None:
    service: Service | None = Service.objects.filter(code=code).first()
    return service


def modifier_by_name(name_en: str) -> PriceModifier | None:
    modifier: PriceModifier | None = PriceModifier.objects.filter(name_en=name_en).first()
    return modifier


def services_by_ids(service_ids: Any) -> list[Service]:
    return list(Service.objects.filter(pk__in=list(service_ids)))


def active_price_list(
    *, branch_id: Any = None, at: datetime | None = None
) -> list[tuple[Service, ServicePrice]]:
    """Active services with the price that applies now, in price-list order. A service
    without a valid price is left out: it can't be ordered."""
    moment = at or timezone.now()
    services = Service.objects.filter(is_active=True, category__is_active=True).select_related(
        "category"
    )
    result: list[tuple[Service, ServicePrice]] = []
    for service in services.order_by("category__position", "position", "name_en"):
        price = price_at(service.pk, branch_id=branch_id, at=moment)
        if price is not None:
            result.append((service, price))
    return result


def active_modifiers() -> list[PriceModifier]:
    return list(PriceModifier.objects.filter(is_active=True).order_by("position", "name_en"))


def modifier_service_ids(modifier: PriceModifier) -> frozenset[str] | None:
    """The services a modifier applies to; None when it applies to all (D-55)."""
    if modifier.applies_to_all:
        return None
    links = PriceModifierService.objects.filter(modifier=modifier)
    return frozenset(str(service_id) for service_id in links.values_list("service_id", flat=True))


# --- Snapshots for the pricing engine --------------------------------------------------


def price_snapshot(service: Service, price: ServicePrice) -> PriceSnapshot:
    return PriceSnapshot(
        service_id=str(service.pk),
        price_id=str(price.pk),
        pricing_model=service.pricing_model,  # type: ignore[arg-type]
        unit=service.unit,
        unit_price=price.unit_price,
        minimum_charge=price.minimum_charge,
        currency=price.currency,
    )


def modifier_snapshot(modifier: PriceModifier) -> ModifierSnapshot:
    return ModifierSnapshot(
        modifier_id=str(modifier.pk),
        percent=modifier.percent,
        amount=modifier.amount,
        service_ids=modifier_service_ids(modifier),
        currency=modifier.currency,
    )
