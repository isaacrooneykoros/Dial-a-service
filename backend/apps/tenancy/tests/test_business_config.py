"""GET /business/config (X-01). It addresses no object, so isolation is shown by each
host getting its own business's data rather than with the 404 harness."""

from typing import Any

import pytest
from django.test import override_settings

from apps.accounts.tests.helpers import client_for
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business, BusinessBranding

pytestmark = pytest.mark.django_db

URL = "/api/v1/business/config"


def config(business: Business) -> Any:
    response = client_for(business).get(URL)
    assert response.status_code == 200
    return response.json()


def test_defaults_without_branding(business_a: Business) -> None:
    body = config(business_a)
    assert body["business"] == {
        "name": "Business-A",
        "slug": "business-a",
        "country": "KE",
        "currency": "KES",
        "timezone": "Africa/Nairobi",
        "language": "en",
    }
    assert body["branding"]["app_name"] == "Business-A"
    assert (body["branding"]["primary_color"], body["branding"]["accent_color"]) == (
        "#0F6B5C",
        "#F2A900",
    )
    assert body["maintenance"] == {"active": False, "expected_return": ""}


def test_each_host_gets_its_own_branding(business_a: Business, business_b: Business) -> None:
    with tenant_context(business_a.id):
        BusinessBranding.objects.create(
            app_name="Mama Safi", primary_color="#2458B3", sms_sender_id="MAMASAFI"
        )
    assert config(business_a)["branding"]["app_name"] == "Mama Safi"
    assert config(business_a)["branding"]["primary_color"] == "#2458B3"
    assert config(business_b)["branding"]["app_name"] == "Business-B"


def test_nothing_internal_is_exposed(business_a: Business) -> None:
    with tenant_context(business_a.id):
        BusinessBranding.objects.create(app_name="Mama Safi", sms_sender_id="MAMASAFI")
    text = str(config(business_a))
    assert "MAMASAFI" not in text
    assert "id" not in config(business_a)["business"]


@override_settings(MAINTENANCE_MODE=True, MAINTENANCE_EXPECTED_RETURN="2026-10-02T06:00:00+03:00")
def test_maintenance_is_platform_wide(business_a: Business, business_b: Business) -> None:
    for business in (business_a, business_b):
        assert config(business)["maintenance"] == {
            "active": True,
            "expected_return": "2026-10-02T06:00:00+03:00",
        }


def test_unknown_host_is_404(db: None) -> None:
    from django.test import Client

    assert Client(headers={"host": "nobody.localhost"}).get(URL).status_code == 404
