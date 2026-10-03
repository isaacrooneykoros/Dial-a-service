"""MoneyField and PercentField: amounts travel as text, never JSON numbers."""

from decimal import Decimal

import pytest
from rest_framework import serializers

from apps.core.api.fields import MoneyField, PercentField


class Amounts(serializers.Serializer[object]):
    price = MoneyField()
    rate = PercentField(required=False)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("120.00", Decimal("120.00")), ("120", Decimal("120")), (" 7.5 ", Decimal("7.5"))],
)
def test_text_amounts_are_exact_decimals(value: str, expected: Decimal) -> None:
    data = Amounts(data={"price": value})
    assert data.is_valid(), data.errors
    assert data.validated_data["price"] == expected
    assert isinstance(data.validated_data["price"], Decimal)


@pytest.mark.parametrize("value", [120.5, 120, True, None])
def test_numbers_are_refused(value: object) -> None:
    data = Amounts(data={"price": value})
    assert not data.is_valid()
    assert "price" in data.errors


def test_the_message_says_what_to_do() -> None:
    data = Amounts(data={"price": 120.5})
    data.is_valid()
    assert data.errors["price"] == ['Send amounts as text, like "120.00".']


@pytest.mark.parametrize("value", ["12.345", "abc", "1,200.00", "12345678901.00"])
def test_badly_formed_text_is_refused(value: str) -> None:
    assert not Amounts(data={"price": value}).is_valid()


def test_output_is_text() -> None:
    assert Amounts({"price": Decimal("120.5"), "rate": Decimal("16")}).data == {
        "price": "120.50",
        "rate": "16.00",
    }


def test_percentages_have_at_most_three_whole_digits() -> None:
    assert not Amounts(data={"price": "1.00", "rate": "1000.00"}).is_valid()
    assert Amounts(data={"price": "1.00", "rate": "999.99"}).is_valid()
