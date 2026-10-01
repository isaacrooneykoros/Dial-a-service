"""The business settings the system knows about (design doc, tenancy.BusinessSetting).

Each setting is declared here once, with its type and safe default; values are
stored per business as JSON in BusinessSetting. Unknown keys and wrong types are
refused, so a typo can never silently create a setting.

M1 declares none: the settings in A-61 (payment timing, cash, reminders, VAT,
limits) arrive with the milestones that use them. Never invent a default for a
business rule here; if one is pending, use a safe default marked
"# TODO(decision): <topic>" and list it in docs/decisions/OPEN.md.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SettingSpec:
    key: str
    type: type
    default: Any
    description: str

    def validate(self, value: Any) -> None:
        # bool is a subclass of int; don't let True pass as an int setting.
        if self.type is int and isinstance(value, bool):
            raise TypeError(f"Setting {self.key!r} must be an int, not a bool.")
        if not isinstance(value, self.type):
            raise TypeError(
                f"Setting {self.key!r} must be {self.type.__name__}, got {type(value).__name__}."
            )


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
