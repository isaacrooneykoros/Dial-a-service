"""GET /app/version (X-01, X-02)."""

import pytest

from apps.accounts.tests.helpers import client_for
from apps.core.models import AppVersion
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

URL = "/api/v1/app/version"


def test_no_row_means_every_version_is_allowed(business_a: Business) -> None:
    assert client_for(business_a).get(URL).json() == {
        "app": "web",
        "platform": "web",
        "minimum": "0.0.0",
        "latest": "0.0.0",
    }


def test_returns_the_configured_versions(business_a: Business) -> None:
    AppVersion.objects.create(app="web", platform="web", minimum="1.2.0", latest="1.4.1")
    AppVersion.objects.create(app="staff", platform="android", minimum="2.0.0", latest="2.1.0")
    assert client_for(business_a).get(URL).json()["minimum"] == "1.2.0"
    android = client_for(business_a).get(URL, {"app": "staff", "platform": "android"}).json()
    assert (android["minimum"], android["latest"]) == ("2.0.0", "2.1.0")
    assert str(AppVersion.objects.get(app="web")) == "web/web 1.2.0..1.4.1"
