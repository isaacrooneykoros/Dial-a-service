"""Shapes for the console catalogue API (M2 T06). Rules live in apps/catalog/services.py."""

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.catalog.models import PriceModifier, Service
from apps.core.api.fields import MoneyField, PercentField, QuantityField


class CategorySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True)
    name_en = serializers.CharField(max_length=120)
    name_sw = serializers.CharField(max_length=120, allow_blank=True, default="")
    position = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class CategoryUpdateSerializer(serializers.Serializer[Any]):
    name_en = serializers.CharField(max_length=120, required=False)
    name_sw = serializers.CharField(max_length=120, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)


class PriceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True)
    branch_id = serializers.UUIDField(read_only=True, allow_null=True)
    unit_price = MoneyField(read_only=True)
    minimum_charge = MoneyField(read_only=True)
    currency = serializers.CharField(read_only=True)
    effective_from = serializers.DateTimeField(read_only=True)
    effective_to = serializers.DateTimeField(read_only=True, allow_null=True)


class PriceCreateSerializer(serializers.Serializer[Any]):
    unit_price = MoneyField()
    # A Decimal, not "0.00": defaults skip the field's parsing.
    minimum_charge = MoneyField(required=False, default=Decimal("0.00"))
    # Now if left out. A start in the past is refused: past orders keep their prices.
    effective_from = serializers.DateTimeField(required=False, allow_null=True, default=None)
    # A branch override; left out for the business-wide price.
    branch_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class ServiceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True)
    category_id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    name_en = serializers.CharField(read_only=True)
    name_sw = serializers.CharField(read_only=True)
    pricing_model = serializers.ChoiceField(choices=Service.PricingModel.choices, read_only=True)
    unit = serializers.ChoiceField(choices=Service.Unit.choices, read_only=True)
    position = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    # The business-wide price in effect now; null if it has none.
    current_price = PriceSerializer(read_only=True, allow_null=True)


class ServiceCreateSerializer(serializers.Serializer[Any]):
    category_id = serializers.UUIDField()
    code = serializers.CharField(max_length=32)
    name_en = serializers.CharField(max_length=120)
    name_sw = serializers.CharField(max_length=120, allow_blank=True, default="")
    pricing_model = serializers.ChoiceField(choices=Service.PricingModel.choices)
    unit = serializers.ChoiceField(choices=Service.Unit.choices)


class ServiceUpdateSerializer(serializers.Serializer[Any]):
    category_id = serializers.UUIDField(required=False)
    name_en = serializers.CharField(max_length=120, required=False)
    name_sw = serializers.CharField(max_length=120, allow_blank=True, required=False)
    pricing_model = serializers.ChoiceField(choices=Service.PricingModel.choices, required=False)
    unit = serializers.ChoiceField(choices=Service.Unit.choices, required=False)


class ReorderSerializer(serializers.Serializer[Any]):
    service_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=500)


class ModifierSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True)
    name_en = serializers.CharField(read_only=True)
    name_sw = serializers.CharField(read_only=True)
    kind = serializers.ChoiceField(choices=PriceModifier.Kind.choices, read_only=True)
    percent = PercentField(read_only=True, allow_null=True)
    amount = MoneyField(read_only=True, allow_null=True)
    currency = serializers.CharField(read_only=True)
    applies_to_all = serializers.BooleanField(read_only=True)
    service_ids = serializers.ListField(child=serializers.UUIDField(), read_only=True)
    position = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class ModifierCreateSerializer(serializers.Serializer[Any]):
    name_en = serializers.CharField(max_length=120)
    name_sw = serializers.CharField(max_length=120, allow_blank=True, default="")
    kind = serializers.ChoiceField(choices=PriceModifier.Kind.choices)
    # Exactly one of these (D-54).
    percent = PercentField(required=False, allow_null=True, default=None)
    amount = MoneyField(required=False, allow_null=True, default=None)
    applies_to_all = serializers.BooleanField(default=True)
    service_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_null=True, default=None, max_length=500
    )


class ModifierUpdateSerializer(serializers.Serializer[Any]):
    name_en = serializers.CharField(max_length=120, required=False)
    name_sw = serializers.CharField(max_length=120, allow_blank=True, required=False)
    percent = PercentField(required=False, allow_null=True)
    amount = MoneyField(required=False, allow_null=True)
    applies_to_all = serializers.BooleanField(required=False)
    service_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, max_length=500
    )
    is_active = serializers.BooleanField(required=False)


class ImportPreviewRequestSerializer(serializers.Serializer[Any]):
    csv = serializers.CharField(trim_whitespace=False)


class ImportApplyRequestSerializer(serializers.Serializer[Any]):
    csv = serializers.CharField(trim_whitespace=False)
    # From the preview: proves the file and the price list are as previewed.
    fingerprint = serializers.CharField(max_length=64, min_length=64)
    effective_from = serializers.DateTimeField(required=False, allow_null=True, default=None)


class ImportRowSerializer(serializers.Serializer[Any]):
    line = serializers.IntegerField()
    service = serializers.CharField()
    category = serializers.CharField(allow_blank=True)
    pricing_model = serializers.CharField(allow_blank=True)
    unit = serializers.CharField(allow_blank=True)
    price = serializers.CharField(allow_blank=True)
    minimum = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=["new", "changed", "unchanged", "invalid"])
    problem = serializers.CharField(allow_blank=True)
    message = serializers.CharField(allow_blank=True)
    old_price = serializers.CharField(allow_null=True)
    old_minimum = serializers.CharField(allow_null=True)
    new_category = serializers.BooleanField()


class ImportCountsSerializer(serializers.Serializer[Any]):
    new = serializers.IntegerField()
    changed = serializers.IntegerField()
    unchanged = serializers.IntegerField()
    invalid = serializers.IntegerField()


class ImportPreviewSerializer(serializers.Serializer[Any]):
    rows = ImportRowSerializer(many=True)
    counts = ImportCountsSerializer()
    fingerprint = serializers.CharField()


# --- Quotes (T08) ----------------------------------------------------------------------------


class QuoteLineRequestSerializer(serializers.Serializer[Any]):
    service_id = serializers.UUIDField()
    # kg for per kg (up to 2 decimals), a whole count for per item, 1 for flat.
    quantity = QuantityField()


class QuoteDiscountRequestSerializer(serializers.Serializer[Any]):
    # Exactly one of percent and amount, with a reason (design doc "Discounts").
    percent = PercentField(required=False, allow_null=True, default=None)
    amount = MoneyField(required=False, allow_null=True, default=None)
    reason = serializers.CharField(max_length=200, allow_blank=True)


class QuoteRequestSerializer(serializers.Serializer[Any]):
    lines = QuoteLineRequestSerializer(many=True, allow_empty=False, max_length=100)
    branch_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    modifier_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=20
    )
    discount = QuoteDiscountRequestSerializer(required=False, allow_null=True, default=None)


class QuoteLineSerializer(serializers.Serializer[Any]):
    service_id = serializers.UUIDField()
    price_id = serializers.UUIDField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    pricing_model = serializers.CharField()
    unit = serializers.CharField()
    quantity = QuantityField()
    unit_price = MoneyField()
    base = MoneyField()
    minimum_applied = serializers.BooleanField()
    modifier_percent = PercentField()
    modifier_ids = serializers.ListField(child=serializers.UUIDField())
    modifier_amount = MoneyField()
    amount = MoneyField()


class QuoteFlatModifierSerializer(serializers.Serializer[Any]):
    modifier_id = serializers.UUIDField()
    amount = MoneyField()


class QuoteSerializer(serializers.Serializer[Any]):
    currency = serializers.CharField()
    lines = QuoteLineSerializer(many=True)
    subtotal = MoneyField()
    flat_modifiers = QuoteFlatModifierSerializer(many=True)
    laundry_total = MoneyField()
    discount = MoneyField()
    delivery_fee = MoneyField()
    taxable = MoneyField()
    vat_registered = serializers.BooleanField()
    vat_rate = PercentField()
    vat_included = serializers.BooleanField()
    vat = MoneyField()
    total_unrounded = MoneyField()
    rounding = MoneyField()
    # Whole shillings: what the customer pays.
    total = MoneyField(decimal_places=0)
    modifiers_not_applied = serializers.ListField(child=serializers.UUIDField())
