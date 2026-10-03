"""The pricing engine: the only place a price is calculated (CLAUDE.md section 6.2).

Design doc "Pricing engine"; owner decisions D-53 (VAT), D-54 (modifiers), D-55
(what a modifier applies to), D-56 (discounts). Pure functions over plain values:
no database, no settings, no request. The catalogue and quote services gather the
inputs (price versions, modifiers, VAT settings, the discount cap) and call quote().

Step by step:

1. Each line's base:
   - per kg: max(minimum charge, kg x rate);
   - per item: quantity x price;
   - flat: the price.
2. Percentage modifiers that apply to the line add up (50% + 10% = 60%, D-54). The
   line amount is base x (1 + total %), rounded to the cent, half-up.
3. Flat-amount modifiers are added once per order (D-54), if at least one line is
   one of the services they apply to (D-55).
4. Laundry total = sum of lines + flat modifiers.
5. Discount: a percent of, or an amount off, the laundry total (D-56), to the cent.
   Refused above the business's cap, so the total never goes below zero.
6. VAT (D-53) is on the taxable amount: the laundry total minus the discount, plus
   the delivery fee (0 until M9).
   - Prices excluding VAT: VAT is added on top, to the cent.
   - Prices including VAT: the VAT is "of which", taken from the rounded total the
     customer actually pays.
   - Not registered: no VAT.
7. Total: rounded half-up to whole shillings, because M-Pesa takes only whole
   amounts. This is the only place that rounding happens. The unrounded total and
   the rounding difference are kept.

Amounts are Decimal throughout, never float.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

PricingModel = Literal["per_kg", "per_item", "flat"]

CENT = Decimal("0.01")
SHILLING = Decimal("1")
HUNDRED = Decimal("100")
ZERO = Decimal("0")
# Most items one line can carry; well beyond any real counter order.
MAX_ITEMS = 9999
# Heaviest line that can be priced (a typo guard, not the S-14 "are you sure" range).
MAX_KG = Decimal("999.99")


class PricingError(ValueError):
    """The inputs can't be priced. ``code`` is stable for the API's error envelope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_shillings(value: Decimal) -> Decimal:
    return value.quantize(SHILLING, rounding=ROUND_HALF_UP)


# --- Inputs ----------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceSnapshot:
    """One price version of one service, exactly as it will be charged."""

    service_id: str
    price_id: str  # the ServicePrice version, so an order can keep exactly what it used
    pricing_model: PricingModel
    unit: str
    unit_price: Decimal
    minimum_charge: Decimal = ZERO  # per kg only
    currency: str = "KES"


@dataclass(frozen=True)
class ModifierSnapshot:
    modifier_id: str
    percent: Decimal | None = None
    amount: Decimal | None = None
    # The services it applies to; None means every service (D-55).
    service_ids: frozenset[str] | None = None
    currency: str = "KES"

    def applies_to(self, service_id: str) -> bool:
        return self.service_ids is None or service_id in self.service_ids


@dataclass(frozen=True)
class LineInput:
    price: PriceSnapshot
    # kg for per kg (up to 2 decimals), a whole count for per item, 1 for flat.
    quantity: Decimal


@dataclass(frozen=True)
class DiscountInput:
    """Exactly one of percent and amount; capped by the business's maximum (D-56)."""

    max_percent: Decimal
    percent: Decimal | None = None
    amount: Decimal | None = None


@dataclass(frozen=True)
class VatInput:
    registered: bool
    rate: Decimal = ZERO
    prices_include_vat: bool = True


# --- Output ----------------------------------------------------------------------------


@dataclass(frozen=True)
class LineResult:
    service_id: str
    price_id: str
    pricing_model: PricingModel
    unit: str
    quantity: Decimal
    unit_price: Decimal
    base: Decimal  # before modifiers, to the cent (the minimum charge when it applied)
    minimum_applied: bool
    modifier_percent: Decimal  # the added-up percentage modifiers on this line
    modifier_ids: tuple[str, ...]  # which percentage modifiers applied
    modifier_amount: Decimal  # amount - base
    amount: Decimal  # the line's total, to the cent


@dataclass(frozen=True)
class FlatModifierResult:
    modifier_id: str
    amount: Decimal


@dataclass(frozen=True)
class Quote:
    currency: str
    lines: tuple[LineResult, ...]
    subtotal: Decimal  # sum of lines
    flat_modifiers: tuple[FlatModifierResult, ...]
    laundry_total: Decimal  # subtotal + flat modifiers
    discount: Decimal
    delivery_fee: Decimal
    taxable: Decimal  # laundry total - discount + delivery fee
    vat_registered: bool
    vat_rate: Decimal
    vat_included: bool  # True: "of which VAT"; False: VAT added on top
    vat: Decimal
    total_unrounded: Decimal
    rounding: Decimal  # total - total_unrounded, within half a shilling either way
    total: Decimal  # whole shillings
    # Modifiers asked for that applied to no line of this order (so nothing was added).
    modifiers_not_applied: tuple[str, ...] = field(default_factory=tuple)


# --- The calculation --------------------------------------------------------------------


def _check_quantity(line: LineInput) -> None:
    quantity, model = line.quantity, line.price.pricing_model
    if model == "per_kg":
        if not ZERO < quantity <= MAX_KG or quantity != quantity.quantize(CENT):
            raise PricingError(
                "bad_quantity", f"Enter a weight from 0.01 to {MAX_KG} kg, to 2 decimal places."
            )
    elif model == "per_item":
        if quantity != quantity.to_integral_value() or not 1 <= quantity <= MAX_ITEMS:
            raise PricingError("bad_quantity", f"Enter a whole number of items, 1 to {MAX_ITEMS}.")
    elif quantity != 1:
        raise PricingError("bad_quantity", "A flat-priced service is charged once per line.")


def _price_line(line: LineInput, percent_modifiers: Sequence[ModifierSnapshot]) -> LineResult:
    _check_quantity(line)
    price = line.price
    if price.pricing_model == "per_kg":
        raw = line.quantity * price.unit_price
        minimum_applied = price.minimum_charge > raw
        raw_base = price.minimum_charge if minimum_applied else raw
    elif price.pricing_model == "per_item":
        raw_base, minimum_applied = line.quantity * price.unit_price, False
    else:
        raw_base, minimum_applied = price.unit_price, False

    applied = [m for m in percent_modifiers if m.applies_to(price.service_id)]
    modifier_percent = sum((m.percent or ZERO for m in applied), ZERO)
    base = to_cents(raw_base)
    amount = to_cents(raw_base * (1 + modifier_percent / HUNDRED))
    return LineResult(
        service_id=price.service_id,
        price_id=price.price_id,
        pricing_model=price.pricing_model,
        unit=price.unit,
        quantity=line.quantity,
        unit_price=price.unit_price,
        base=base,
        minimum_applied=minimum_applied,
        modifier_percent=modifier_percent,
        modifier_ids=tuple(m.modifier_id for m in applied),
        modifier_amount=amount - base,
        amount=amount,
    )


def _discount(laundry_total: Decimal, discount: DiscountInput | None) -> Decimal:
    if discount is None:
        return ZERO
    percent, amount = discount.percent, discount.amount
    if percent is not None and amount is None:
        if percent <= 0:
            raise PricingError("bad_discount", "A discount must be more than zero.")
        value = to_cents(laundry_total * percent / HUNDRED)
        over_cap = percent > discount.max_percent
    elif amount is not None and percent is None:
        if amount <= 0 or amount != amount.quantize(CENT):
            raise PricingError("bad_discount", "A discount must be more than zero, to the cent.")
        value = amount
        over_cap = value > to_cents(laundry_total * discount.max_percent / HUNDRED)
    else:
        raise PricingError("bad_discount", "Give the discount as a percentage or an amount.")
    if over_cap:
        raise PricingError(
            "discount_over_cap",
            f"The most this business allows is {discount.max_percent.normalize():f}% off.",
        )
    return value


def quote(
    lines: Sequence[LineInput],
    *,
    modifiers: Sequence[ModifierSnapshot] = (),
    discount: DiscountInput | None = None,
    vat: VatInput,
    delivery_fee: Decimal = ZERO,
    currency: str = "KES",
) -> Quote:
    """Price an order. Raises PricingError for anything that can't be priced."""
    if not lines:
        raise PricingError("no_lines", "Add at least one service.")
    if len({m.modifier_id for m in modifiers}) != len(modifiers):
        raise PricingError("duplicate_modifier", "Each modifier can be chosen once.")
    currencies = {line.price.currency for line in lines} | {m.currency for m in modifiers}
    if currencies != {currency}:
        raise PricingError("currency_mismatch", f"Prices must all be in {currency}.")
    for m in modifiers:
        if (m.percent is None) == (m.amount is None) or (m.percent or m.amount or ZERO) <= 0:
            raise PricingError("bad_modifier", "A modifier is a positive percentage or amount.")
    if delivery_fee < 0 or delivery_fee != delivery_fee.quantize(CENT):
        raise PricingError(
            "bad_delivery_fee", "The delivery fee must be zero or more, to the cent."
        )
    if vat.registered and not ZERO <= vat.rate <= HUNDRED:
        raise PricingError("bad_vat_rate", "The VAT rate must be from 0 to 100%.")

    percent_modifiers = [m for m in modifiers if m.percent is not None]
    flat_candidates = [m for m in modifiers if m.amount is not None]
    priced = tuple(_price_line(line, percent_modifiers) for line in lines)
    service_ids = {line.service_id for line in priced}

    flat = tuple(
        FlatModifierResult(m.modifier_id, m.amount)
        for m in flat_candidates
        if m.amount is not None and any(m.applies_to(s) for s in service_ids)
    )
    used = {mid for line in priced for mid in line.modifier_ids} | {f.modifier_id for f in flat}
    not_applied = tuple(m.modifier_id for m in modifiers if m.modifier_id not in used)

    subtotal = sum((line.amount for line in priced), ZERO)
    laundry_total = subtotal + sum((f.amount for f in flat), ZERO)
    discount_value = _discount(laundry_total, discount)
    taxable = laundry_total - discount_value + delivery_fee

    if not vat.registered:
        vat_value, total_unrounded = ZERO, taxable
        total = to_shillings(total_unrounded)
    elif vat.prices_include_vat:
        total_unrounded = taxable
        total = to_shillings(total_unrounded)
        # "Of which VAT", from what the customer actually pays.
        vat_value = to_cents(total * vat.rate / (HUNDRED + vat.rate))
    else:
        vat_value = to_cents(taxable * vat.rate / HUNDRED)
        total_unrounded = taxable + vat_value
        total = to_shillings(total_unrounded)

    return Quote(
        currency=currency,
        lines=priced,
        subtotal=subtotal,
        flat_modifiers=flat,
        laundry_total=laundry_total,
        discount=discount_value,
        delivery_fee=delivery_fee,
        taxable=taxable,
        vat_registered=vat.registered,
        vat_rate=vat.rate if vat.registered else ZERO,
        vat_included=vat.registered and vat.prices_include_vat,
        vat=vat_value,
        total_unrounded=total_unrounded,
        rounding=total - total_unrounded,
        total=total,
        modifiers_not_applied=not_applied,
    )
