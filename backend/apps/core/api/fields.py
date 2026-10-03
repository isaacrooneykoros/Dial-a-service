"""Serializer fields shared by every app's API."""

from decimal import Decimal
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class MoneyField(serializers.DecimalField):
    """An amount sent and returned as text ("120.00"), never a JSON number.

    JSON numbers become floats, and money never touches floats (CLAUDE.md section
    6.2). So a number is refused with a clear message instead of being converted.
    """

    default_error_messages = {
        "not_text": _('Send amounts as text, like "120.00".'),
    }

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("coerce_to_string", True)
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> Decimal:
        if not isinstance(data, str):
            self.fail("not_text")
        value: Decimal = super().to_internal_value(data.strip())
        return value


class QuantityField(MoneyField):
    """A weight or count as text ("6.40", "2"): exact, never a float."""

    default_error_messages = {
        "not_text": _('Send quantities as text, like "6.40".'),
    }

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 7)
        super().__init__(**kwargs)


class PercentField(MoneyField):
    """A percentage as text ("16.00"), at most 2 decimal places."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 5)
        super().__init__(**kwargs)
