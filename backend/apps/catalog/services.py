"""Changes to the catalogue: categories, services, price versions, modifiers (M2 T04).

Design doc "Pricing engine" (versions and snapshots), A-30 rules, owner decisions
D-54 to D-58. Every change writes an AuditLog row with before and after values;
amounts in audit rows are strings, never floats.

Price versions:
- A new price takes effect from now or a later time, never the past: a past start
  would change what past orders were charged.
- It closes the version in effect at its start. If a later version is already
  scheduled, the new one runs until that one starts.
- A scheduled version that hasn't started yet is replaced by setting a price with
  exactly the same start. Versions that have started are read-only.
- Price changes for one service are serialised by locking the service row, and the
  database refuses overlaps in any case (T01).
"""

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.branches.selectors import branches_by_ids
from apps.catalog import selectors, templates
from apps.catalog.models import (
    PriceModifier,
    PriceModifierService,
    Service,
    ServiceCategory,
    ServicePrice,
)
from apps.core import audit
from apps.core.tenant_context import get_current_business_id
from apps.tenancy.selectors import business_currency

CENT = Decimal("0.01")
# Largest amount a DecimalField(12, 2) holds.
MAX_AMOUNT = Decimal("9999999999.99")
MAX_PERCENT = Decimal("999.99")
# A start a moment in the past (the request took a while) is treated as "now".
CLOCK_SKEW = timedelta(minutes=1)


class CatalogError(Exception):
    """A change the catalogue refuses. ``code`` is stable for the API; ``field`` names
    the input it's about, if any."""

    def __init__(self, code: str, field: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.field = field


def _money(value: Decimal, *, field: str, allow_zero: bool = False) -> Decimal:
    if not isinstance(value, Decimal):
        raise CatalogError("bad_amount", field)
    if value != value.quantize(CENT) or value > MAX_AMOUNT or value < 0:
        raise CatalogError("bad_amount", field)
    if value == 0 and not allow_zero:
        raise CatalogError("bad_amount", field)
    return value


def _price_audit(price: ServicePrice | None) -> dict[str, Any] | None:
    if price is None:
        return None
    return {
        "unit_price": str(price.unit_price),
        "minimum_charge": str(price.minimum_charge),
        "currency": price.currency,
        "branch_id": str(price.branch_id) if price.branch_id else None,
        "effective_from": price.effective_from.isoformat(),
        "effective_to": price.effective_to.isoformat() if price.effective_to else None,
    }


def _next_position(model: type[ServiceCategory] | type[Service] | type[PriceModifier]) -> int:
    highest = model.objects.aggregate(highest=Max("position"))["highest"]
    return 0 if highest is None else int(highest) + 1


# --- Categories --------------------------------------------------------------------------


def create_category(
    *, name_en: str, name_sw: str = "", actor: Any = None, request: Any = None
) -> ServiceCategory:
    name_en = name_en.strip()
    if not name_en:
        raise CatalogError("name_required", "name_en")
    try:
        with transaction.atomic():
            category: ServiceCategory = ServiceCategory.objects.create(
                name_en=name_en,
                name_sw=name_sw.strip(),
                position=_next_position(ServiceCategory),
            )
    except IntegrityError as exc:
        raise CatalogError("duplicate_name", "name_en") from exc
    audit.record(
        "catalog.category.create",
        obj=category,
        after={"name_en": name_en},
        actor=actor,
        request=request,
    )
    return category


def update_category(
    category: ServiceCategory,
    *,
    name_en: str | None = None,
    name_sw: str | None = None,
    is_active: bool | None = None,
    actor: Any = None,
    request: Any = None,
) -> ServiceCategory:
    before = {
        "name_en": category.name_en,
        "name_sw": category.name_sw,
        "is_active": category.is_active,
    }
    if name_en is not None:
        if not name_en.strip():
            raise CatalogError("name_required", "name_en")
        category.name_en = name_en.strip()
    if name_sw is not None:
        category.name_sw = name_sw.strip()
    if is_active is not None:
        category.is_active = is_active
    try:
        with transaction.atomic():
            category.save()
    except IntegrityError as exc:
        category.refresh_from_db()  # don't leave the refused values on the object
        raise CatalogError("duplicate_name", "name_en") from exc
    after = {
        "name_en": category.name_en,
        "name_sw": category.name_sw,
        "is_active": category.is_active,
    }
    audit.record(
        "catalog.category.update",
        obj=category,
        before=before,
        after=after,
        actor=actor,
        request=request,
    )
    return category


# --- Services ----------------------------------------------------------------------------


def _check_unit(pricing_model: str, unit: str) -> None:
    if pricing_model not in Service.PricingModel.values:
        raise CatalogError("bad_pricing_model", "pricing_model")
    if unit not in Service.Unit.values:
        raise CatalogError("bad_unit", "unit")
    # D-58: per kg always shows kg; the others use item, pair or set.
    if (pricing_model == Service.PricingModel.PER_KG) != (unit == Service.Unit.KG):
        raise CatalogError("unit_mismatch", "unit")


def _service_audit(service: Service) -> dict[str, Any]:
    return {
        "category_id": str(service.category_id),
        "code": service.code,
        "name_en": service.name_en,
        "name_sw": service.name_sw,
        "pricing_model": service.pricing_model,
        "unit": service.unit,
        "is_active": service.is_active,
    }


def create_service(
    *,
    category: ServiceCategory,
    code: str,
    name_en: str,
    pricing_model: str,
    unit: str,
    name_sw: str = "",
    actor: Any = None,
    request: Any = None,
) -> Service:
    """A new service, switched off until it has a price (D-57)."""
    _check_unit(pricing_model, unit)
    service = Service(
        category=category,
        code=code.strip(),
        name_en=name_en.strip(),
        name_sw=name_sw.strip(),
        pricing_model=pricing_model,
        unit=unit,
        position=_next_position(Service),
        is_active=False,
    )
    try:
        service.full_clean(exclude=["business", "category"])
    except ValidationError as exc:
        field = next(iter(exc.message_dict), None)
        raise CatalogError("name_required" if field == "name_en" else "bad_code", field) from exc
    try:
        with transaction.atomic():
            service.save()
    except IntegrityError as exc:
        raise CatalogError("duplicate_code", "code") from exc
    audit.record(
        "catalog.service.create",
        obj=service,
        after=_service_audit(service),
        actor=actor,
        request=request,
    )
    return service


def update_service(
    service: Service,
    *,
    category: ServiceCategory | None = None,
    name_en: str | None = None,
    name_sw: str | None = None,
    pricing_model: str | None = None,
    unit: str | None = None,
    actor: Any = None,
    request: Any = None,
) -> Service:
    """Rename, move to another category, or (before it has any price) change how it's
    priced. Once a service has a price, its pricing model and unit are fixed, so old
    prices keep their meaning; a different model needs a new service."""
    before = _service_audit(service)
    new_model = pricing_model if pricing_model is not None else service.pricing_model
    new_unit = unit if unit is not None else service.unit
    if (new_model, new_unit) != (service.pricing_model, service.unit):
        if selectors.has_prices(service.pk):
            raise CatalogError("pricing_model_locked", "pricing_model")
        _check_unit(new_model, new_unit)
        service.pricing_model, service.unit = new_model, new_unit
    if category is not None:
        service.category = category
    if name_en is not None:
        if not name_en.strip():
            raise CatalogError("name_required", "name_en")
        service.name_en = name_en.strip()
    if name_sw is not None:
        service.name_sw = name_sw.strip()
    service.save()
    audit.record(
        "catalog.service.update",
        obj=service,
        before=before,
        after=_service_audit(service),
        actor=actor,
        request=request,
    )
    return service


def set_service_active(
    service: Service, active: bool, *, actor: Any = None, request: Any = None
) -> Service:
    """Switch a service on or off. Switching on needs a business-wide price in effect
    now. Services are never deleted, so past orders always find them (A-30)."""
    if active and selectors.price_at(service.pk) is None:
        raise CatalogError("needs_price", "is_active")
    before = service.is_active
    service.is_active = active
    service.save(update_fields=["is_active", "updated_at"])
    audit.record(
        "catalog.service.activate" if active else "catalog.service.deactivate",
        obj=service,
        before={"is_active": before},
        after={"is_active": active},
        actor=actor,
        request=request,
    )
    return service


def reorder_services(
    service_ids: Sequence[Any], *, actor: Any = None, request: Any = None
) -> list[Service]:
    """Put services in this order (the staff app's quick-add buttons, A-30)."""
    ids = [str(service_id) for service_id in service_ids]
    if len(set(ids)) != len(ids):
        raise CatalogError("duplicate_service", "service_ids")
    services = {str(s.pk): s for s in selectors.services_by_ids(ids)}
    if len(services) != len(ids):
        raise CatalogError("unknown_service", "service_ids")
    ordered = [services[service_id] for service_id in ids]
    with transaction.atomic():
        for position, service in enumerate(ordered):
            if service.position != position:
                service.position = position
                service.save(update_fields=["position", "updated_at"])
    audit.record(
        "catalog.services.reorder",
        object_type="catalog.service",
        after={"order": ids},
        actor=actor,
        request=request,
    )
    return ordered


# --- Prices ------------------------------------------------------------------------------


def set_price(
    service: Service,
    *,
    unit_price: Decimal,
    minimum_charge: Decimal = Decimal("0.00"),
    effective_from: datetime | None = None,
    branch_id: Any = None,
    actor: Any = None,
    request: Any = None,
) -> ServicePrice:
    """A new price version for a service, business-wide or for one branch."""
    _money(unit_price, field="unit_price")
    _money(minimum_charge, field="minimum_charge", allow_zero=True)
    if minimum_charge and service.pricing_model != Service.PricingModel.PER_KG:
        raise CatalogError("minimum_per_kg_only", "minimum_charge")

    now = timezone.now()
    start = effective_from or now
    if timezone.is_naive(start):
        raise CatalogError("bad_start", "effective_from")
    if start < now - CLOCK_SKEW:
        raise CatalogError("starts_in_past", "effective_from")
    start = max(start, now)

    if branch_id is not None and not branches_by_ids([branch_id]):
        raise CatalogError("unknown_branch", "branch_id")
    currency = business_currency(get_current_business_id())

    try:
        with transaction.atomic():
            # One price change per service at a time.
            Service.objects.select_for_update().filter(pk=service.pk).first()
            versions = ServicePrice.objects.filter(
                service=service, branch_id=branch_id
            ).select_for_update()
            scheduled: ServicePrice | None = versions.filter(effective_from=start).first()
            if scheduled is not None:
                # Not started yet (start is now or later): replace its amounts.
                before = _price_audit(scheduled)
                scheduled.unit_price, scheduled.minimum_charge = unit_price, minimum_charge
                scheduled.created_by = actor or scheduled.created_by
                scheduled.save()
                audit.record(
                    "catalog.price.set",
                    obj=scheduled,
                    before=before,
                    after=_price_audit(scheduled),
                    actor=actor,
                    request=request,
                )
                return scheduled

            current = versions.filter(
                Q(effective_from__lt=start),
                Q(effective_to__isnull=True) | Q(effective_to__gt=start),
            ).first()
            following = versions.filter(effective_from__gt=start).order_by("effective_from").first()
            before = _price_audit(current)
            end = following.effective_from if following is not None else None
            if current is not None:
                if current.effective_to is not None and (end is None or current.effective_to < end):
                    end = current.effective_to
                current.effective_to = start
                current.save(update_fields=["effective_to", "updated_at"])
            price: ServicePrice = ServicePrice.objects.create(
                service=service,
                branch_id=branch_id,
                unit_price=unit_price,
                minimum_charge=minimum_charge,
                currency=currency,
                effective_from=start,
                effective_to=end,
                created_by=actor,
            )
    except IntegrityError as exc:
        raise CatalogError("price_conflict", "effective_from") from exc
    audit.record(
        "catalog.price.set",
        obj=price,
        before=before,
        after=_price_audit(price),
        actor=actor,
        request=request,
    )
    return price


# --- Modifiers ---------------------------------------------------------------------------


def _check_modifier_value(percent: Decimal | None, amount: Decimal | None) -> None:
    if (percent is None) == (amount is None):
        raise CatalogError("percent_or_amount", "percent")
    if percent is not None:
        if not isinstance(percent, Decimal) or percent != percent.quantize(CENT):
            raise CatalogError("bad_percent", "percent")
        if not Decimal("0") < percent <= MAX_PERCENT:
            raise CatalogError("bad_percent", "percent")
    if amount is not None:
        _money(amount, field="amount")


def _link_services(modifier: PriceModifier, service_ids: Iterable[Any] | None) -> None:
    PriceModifierService.objects.filter(modifier=modifier).delete()
    if modifier.applies_to_all:
        if service_ids:
            # A list for a modifier that applies to every service is a contradiction.
            raise CatalogError("applies_to_all", "service_ids")
        return
    ids = [str(service_id) for service_id in service_ids or []]
    services = selectors.services_by_ids(ids)
    if not ids or len(services) != len(set(ids)):
        raise CatalogError("unknown_service", "service_ids")
    PriceModifierService.objects.bulk_create(
        [PriceModifierService(modifier=modifier, service=service) for service in services]
    )


def _modifier_audit(modifier: PriceModifier) -> dict[str, Any]:
    return {
        "name_en": modifier.name_en,
        "name_sw": modifier.name_sw,
        "kind": modifier.kind,
        "percent": str(modifier.percent) if modifier.percent is not None else None,
        "amount": str(modifier.amount) if modifier.amount is not None else None,
        "applies_to_all": modifier.applies_to_all,
        "service_ids": sorted(selectors.modifier_service_ids(modifier) or []),
        "is_active": modifier.is_active,
    }


def create_modifier(
    *,
    name_en: str,
    kind: str,
    percent: Decimal | None = None,
    amount: Decimal | None = None,
    name_sw: str = "",
    applies_to_all: bool = True,
    service_ids: Iterable[Any] | None = None,
    actor: Any = None,
    request: Any = None,
) -> PriceModifier:
    """Express or a chargeable preference: a percentage per line or an amount once per
    order (D-54), for all services or a chosen list (D-55)."""
    if kind not in PriceModifier.Kind.values:
        raise CatalogError("bad_kind", "kind")
    if not name_en.strip():
        raise CatalogError("name_required", "name_en")
    _check_modifier_value(percent, amount)
    try:
        with transaction.atomic():
            modifier: PriceModifier = PriceModifier.objects.create(
                name_en=name_en.strip(),
                name_sw=name_sw.strip(),
                kind=kind,
                percent=percent,
                amount=amount,
                currency=business_currency(get_current_business_id()),
                applies_to_all=applies_to_all,
                position=_next_position(PriceModifier),
            )
            _link_services(modifier, service_ids)
    except IntegrityError as exc:
        raise CatalogError("duplicate_name", "name_en") from exc
    audit.record(
        "catalog.modifier.create",
        obj=modifier,
        after=_modifier_audit(modifier),
        actor=actor,
        request=request,
    )
    return modifier


def update_modifier(
    modifier: PriceModifier,
    *,
    name_en: str | None = None,
    name_sw: str | None = None,
    percent: Decimal | None = None,
    amount: Decimal | None = None,
    applies_to_all: bool | None = None,
    service_ids: Iterable[Any] | None = None,
    is_active: bool | None = None,
    actor: Any = None,
    request: Any = None,
) -> PriceModifier:
    """Change a modifier. Giving a percent or an amount replaces the value (so an amount
    can become a percentage); it applies to new quotes only, never past orders."""
    before = _modifier_audit(modifier)
    if name_en is not None:
        if not name_en.strip():
            raise CatalogError("name_required", "name_en")
        modifier.name_en = name_en.strip()
    if name_sw is not None:
        modifier.name_sw = name_sw.strip()
    if percent is not None or amount is not None:
        _check_modifier_value(percent, amount)
        modifier.percent, modifier.amount = percent, amount
    if is_active is not None:
        modifier.is_active = is_active
    relink = applies_to_all is not None or service_ids is not None
    if applies_to_all is not None:
        modifier.applies_to_all = applies_to_all
    try:
        with transaction.atomic():
            modifier.save()
            if relink:
                if service_ids is None and not modifier.applies_to_all:
                    # Switching to a chosen list without giving one keeps the existing links.
                    service_ids = selectors.modifier_service_ids(modifier) or []
                _link_services(modifier, service_ids)
    except IntegrityError as exc:
        modifier.refresh_from_db()  # don't leave the refused values on the object
        raise CatalogError("duplicate_name", "name_en") from exc
    except CatalogError:
        modifier.refresh_from_db()
        raise
    action = "catalog.modifier.update"
    audit.record(
        action,
        obj=modifier,
        before=before,
        after=_modifier_audit(modifier),
        actor=actor,
        request=request,
    )
    return modifier


# --- The starting price list (D-57) ------------------------------------------------------


def install_template(*, actor: Any = None, request: Any = None) -> list[Service]:
    """Add the template categories and services the business doesn't have yet.

    Safe to run again: categories are matched by name and services by code, so
    nothing is duplicated and nothing the owner changed is touched. Everything is
    unpriced and switched off until the owner sets prices.
    """
    categories = {c.name_en: c for c in ServiceCategory.objects.all()}
    for category in templates.CATEGORIES:
        if category.name_en not in categories:
            categories[category.name_en] = create_category(
                name_en=category.name_en, actor=actor, request=request
            )
    existing = set(Service.objects.values_list("code", flat=True))
    created: list[Service] = []
    for template in templates.SERVICES:
        if template.code in existing:
            continue
        created.append(
            create_service(
                category=categories[template.category],
                code=template.code,
                name_en=template.name_en,
                pricing_model=template.pricing_model,
                unit=template.unit,
                actor=actor,
                request=request,
            )
        )
    return created
