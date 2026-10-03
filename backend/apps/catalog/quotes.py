"""Quotes: price an order without saving anything (M2 T08).

The same calculation serves S-14's live preview (M3), A-30's calculator (M5) and,
from M9, customer estimates. It gathers the inputs (the price versions in effect
at the branch, the modifiers, VAT settings and the discount cap) and hands them to
apps/catalog/pricing.py, the only place prices are calculated.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.accounts.models import Role
from apps.branches.selectors import branches_by_ids
from apps.catalog import pricing, selectors
from apps.catalog.models import PriceModifier, Service
from apps.core.tenant_context import get_current_business_id
from apps.tenancy.selectors import business_currency, decimal_setting, get_setting

# Who may give a discount (11-staff-app.md: staff only with the right; managers yes).
ALWAYS_DISCOUNT = (Role.OWNER, Role.MANAGER)


class QuoteError(Exception):
    """Something in the request can't be quoted. ``field`` names the input."""

    def __init__(self, code: str, field: str | None = None, **detail: Any) -> None:
        super().__init__(code)
        self.code = code
        self.field = field
        self.detail = detail


@dataclass(frozen=True)
class QuoteLine:
    service_id: Any
    quantity: Decimal


@dataclass(frozen=True)
class DiscountRequest:
    reason: str
    percent: Decimal | None = None
    amount: Decimal | None = None


@dataclass(frozen=True)
class QuoteResult:
    quote: pricing.Quote
    services: dict[str, Service]  # by ID, for names and units in the response


def can_discount(user: Any) -> bool:
    return bool(user.role in ALWAYS_DISCOUNT or getattr(user, "can_give_discounts", False))


def build_quote(
    lines: Sequence[QuoteLine],
    *,
    user: Any,
    branch_id: Any = None,
    modifier_ids: Sequence[Any] = (),
    discount: DiscountRequest | None = None,
) -> QuoteResult:
    if branch_id is not None and not branches_by_ids([branch_id]):
        raise QuoteError("unknown_branch", "branch_id")

    found = {str(s.pk): s for s in selectors.services_by_ids([line.service_id for line in lines])}
    inputs: list[pricing.LineInput] = []
    for index, line in enumerate(lines):
        service = found.get(str(line.service_id))
        if service is None:
            raise QuoteError("unknown_service", f"lines.{index}.service_id")
        if not service.is_active:
            raise QuoteError("service_off", f"lines.{index}.service_id", name=service.name_en)
        price = selectors.price_at(service.pk, branch_id=branch_id)
        if price is None:
            raise QuoteError("no_price", f"lines.{index}.service_id", name=service.name_en)
        line_input = pricing.LineInput(selectors.price_snapshot(service, price), line.quantity)
        try:
            pricing.check_quantity(line_input)
        except pricing.PricingError as exc:
            raise QuoteError(exc.code, f"lines.{index}.quantity") from exc
        inputs.append(line_input)

    ids = [str(modifier_id) for modifier_id in modifier_ids]
    modifiers = {str(m.pk): m for m in PriceModifier.objects.filter(pk__in=ids, is_active=True)}
    if len(set(ids)) != len(ids):
        raise QuoteError("duplicate_modifier", "modifier_ids")
    if len(modifiers) != len(ids):
        raise QuoteError("unknown_modifier", "modifier_ids")

    discount_input = None
    if discount is not None:
        if not can_discount(user):
            raise QuoteError("no_discount_right", "discount")
        if not discount.reason.strip():
            raise QuoteError("discount_reason_required", "discount.reason")
        discount_input = pricing.DiscountInput(
            max_percent=decimal_setting("discounts.max_percent"),
            percent=discount.percent,
            amount=discount.amount,
        )

    vat = pricing.VatInput(
        registered=bool(get_setting("vat.registered")),
        rate=decimal_setting("vat.rate"),
        prices_include_vat=bool(get_setting("vat.prices_include_vat")),
    )
    try:
        quote = pricing.quote(
            inputs,
            modifiers=[selectors.modifier_snapshot(modifiers[mid]) for mid in ids],
            discount=discount_input,
            vat=vat,
            currency=business_currency(get_current_business_id()),
        )
    except pricing.PricingError as exc:
        raise QuoteError(exc.code, _field_for(exc.code)) from exc
    return QuoteResult(quote=quote, services=found)


def _field_for(code: str) -> str | None:
    if code in ("discount_over_cap", "bad_discount"):
        return "discount"
    return None
