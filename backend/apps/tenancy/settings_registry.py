"""The business settings the system knows about (design doc, tenancy.BusinessSetting).

Each setting is declared here once, with its type and safe default; values are
stored per business as JSON in BusinessSetting. Unknown keys and wrong types are
refused, so a typo can never silently create a setting.

Settings arrive with the milestones that use them (A-61 lists them all). M2
declares the money settings: VAT and the discount cap. Never invent a default for
a business rule here; if one is pending, use a safe default marked
"# TODO(decision): <topic>" and list it in docs/decisions/OPEN.md.

Percentages are stored as decimal strings ("16.00"), never JSON numbers: JSON
numbers become floats, and money maths never uses floats (CLAUDE.md section 6.2).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

_PERCENT = re.compile(r"^\d{1,3}(\.\d{1,2})?$")


@dataclass(frozen=True)
class SettingSpec:
    key: str
    type: type
    default: Any
    description: str
    # Extra rule beyond the type, such as a range; raises ValueError.
    check: Callable[[Any], None] | None = None

    def validate(self, value: Any) -> None:
        # bool is a subclass of int; don't let True pass as an int setting.
        if self.type is int and isinstance(value, bool):
            raise TypeError(f"Setting {self.key!r} must be an int, not a bool.")
        if not isinstance(value, self.type):
            raise TypeError(
                f"Setting {self.key!r} must be {self.type.__name__}, got {type(value).__name__}."
            )
        if self.check is not None:
            self.check(value)


SETTINGS: dict[str, SettingSpec] = {}


def register(spec: SettingSpec) -> SettingSpec:
    if spec.key in SETTINGS:
        raise ValueError(f"Setting {spec.key!r} is already registered.")
    spec.validate(spec.default)
    SETTINGS[spec.key] = spec
    return spec


def get_spec(key: str) -> SettingSpec:
    try:
        return SETTINGS[key]
    except KeyError:
        raise KeyError(f"Unknown business setting {key!r}.") from None


def percent_between(low: str, high: str) -> Callable[[Any], None]:
    """A percentage as a decimal string with at most 2 decimals, within [low, high]."""

    def check(value: Any) -> None:
        if not isinstance(value, str) or not _PERCENT.fullmatch(value):
            raise ValueError(f"Use a percentage like 16 or 16.00, not {value!r}.")
        if not Decimal(low) <= Decimal(value) <= Decimal(high):
            raise ValueError(f"Use a percentage from {low} to {high}.")

    return check


# --- Money (M2) ---------------------------------------------------------------------
VAT_REGISTERED = register(
    SettingSpec("vat.registered", bool, False, "The business is registered for VAT (D-53).")
)
VAT_RATE = register(
    SettingSpec(
        "vat.rate",
        str,
        "16.00",  # D-53: start at Kenya's standard rate; the owner can change it.
        "VAT rate in percent, for a VAT-registered business (D-53).",
        percent_between("0", "100"),
    )
)
VAT_PRICES_INCLUDE_VAT = register(
    SettingSpec(
        "vat.prices_include_vat",
        bool,
        # TODO(decision): vat-prices-include (D-61). Safe default: the listed price is
        # what the customer pays, and nothing is added on top unexpectedly.
        True,
        "Listed prices already include VAT (shown as 'of which VAT'); otherwise it's added.",
    )
)
DISCOUNT_MAX_PERCENT = register(
    SettingSpec(
        "discounts.max_percent",
        str,
        "0.00",  # D-56: no discounts until the owner sets a cap.
        "The largest discount, in percent of the laundry total (D-56).",
        percent_between("0", "100"),
    )
)
