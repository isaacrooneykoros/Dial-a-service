"""The price list in GET /business/config (M2 T09; owner decision D-59).

Public, so only what customers see when booking anyway: active services with the
business-wide price in effect now, their categories, active modifiers, and how VAT
is shown. Price history, switched-off services and branch overrides stay
signed-in only (the console API). The staff app's real prices at a branch come
from quotes.
"""

from typing import Any

from rest_framework import serializers

from apps.catalog import selectors
from apps.catalog.models import PriceModifier, Service
from apps.core.api.fields import MoneyField, PercentField
from apps.tenancy.config_sections import ConfigSection
from apps.tenancy.selectors import decimal_setting, get_setting


class ConfigCategorySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    position = serializers.IntegerField()


class ConfigServiceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    category_id = serializers.UUIDField()
    code = serializers.CharField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    pricing_model = serializers.ChoiceField(choices=Service.PricingModel.choices)
    unit = serializers.ChoiceField(choices=Service.Unit.choices)
    # Order of the staff app's quick-add buttons.
    position = serializers.IntegerField()
    unit_price = MoneyField()
    minimum_charge = MoneyField()
    currency = serializers.CharField()


class ConfigModifierSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    kind = serializers.ChoiceField(choices=PriceModifier.Kind.choices)
    percent = PercentField(allow_null=True)
    amount = MoneyField(allow_null=True)
    applies_to_all = serializers.BooleanField()
    service_ids = serializers.ListField(child=serializers.UUIDField())


class ConfigVatSerializer(serializers.Serializer[Any]):
    registered = serializers.BooleanField()
    rate = PercentField()
    prices_include_vat = serializers.BooleanField()


class ConfigCatalogSerializer(serializers.Serializer[Any]):
    categories = ConfigCategorySerializer(many=True)
    services = ConfigServiceSerializer(many=True)
    modifiers = ConfigModifierSerializer(many=True)
    vat = ConfigVatSerializer()


def catalog_config() -> dict[str, Any]:
    listed = selectors.active_price_list()
    categories: dict[str, Any] = {}
    services = []
    for service, price in listed:
        categories.setdefault(str(service.category_id), service.category)
        services.append(
            {
                "id": service.pk,
                "category_id": service.category_id,
                "code": service.code,
                "name_en": service.name_en,
                "name_sw": service.name_sw,
                "pricing_model": service.pricing_model,
                "unit": service.unit,
                "position": service.position,
                "unit_price": price.unit_price,
                "minimum_charge": price.minimum_charge,
                "currency": price.currency,
            }
        )
    modifiers = []
    for modifier in selectors.active_modifiers():
        ids = selectors.modifier_service_ids(modifier)
        modifiers.append(
            {
                "id": modifier.pk,
                "name_en": modifier.name_en,
                "name_sw": modifier.name_sw,
                "kind": modifier.kind,
                "percent": modifier.percent,
                "amount": modifier.amount,
                "applies_to_all": modifier.applies_to_all,
                "service_ids": sorted(ids) if ids is not None else [],
            }
        )
    return {
        "categories": sorted(categories.values(), key=lambda c: (c.position, c.name_en)),
        "services": services,
        "modifiers": modifiers,
        "vat": {
            "registered": bool(get_setting("vat.registered")),
            "rate": decimal_setting("vat.rate"),
            "prices_include_vat": bool(get_setting("vat.prices_include_vat")),
        },
    }


SECTION = ConfigSection(name="catalog", serializer=ConfigCatalogSerializer, build=catalog_config)
