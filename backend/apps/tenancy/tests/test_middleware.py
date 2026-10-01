"""Host resolution and the per-request tenant transaction (M1 T04c, ADR-0001 sections 1 and 2)."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
import time_machine
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext

from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business
from apps.tenancy.selectors import forget_host
from apps.tenancy.tests.factories import BusinessDomainFactory
from tests.testapp.models import Widget

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.testapp.urls")]

HOST = "mamasafi.localhost"


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def business() -> Business:
    domain = BusinessDomainFactory(host=HOST, business__slug="mamasafi")
    business: Business = domain.business
    return business


def get(path: str, host: str = HOST, client: Client | None = None) -> Any:
    return (client or Client()).get(path, headers={"host": host})


def domain_lookups(action: Callable[[], object]) -> int:
    """How many queries hit BusinessDomain while running ``action``."""
    with CaptureQueriesContext(connection) as captured:
        action()
    return sum("tenancy_businessdomain" in query["sql"] for query in captured.captured_queries)


def widget_names(business: Business) -> list[str]:
    with tenant_context(business.id):
        return list(Widget.objects.values_list("name", flat=True))


class TestResolution:
    def test_known_host_sets_the_business(self, business: Business) -> None:
        body = get("/t/whoami").json()
        assert body["business_id"] == str(business.id)

    def test_port_and_case_are_ignored(self, business: Business) -> None:
        body = get("/t/whoami", host="MamaSafi.localhost:5173").json()
        assert body["business_id"] == str(business.id)

    def test_unknown_host_gets_404_before_any_view(self) -> None:
        response = get("/t/whoami", host="nobody.localhost")
        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "not_found"
        assert body["request_id"] == response["X-Request-ID"]
        assert "business_id" not in body  # the view never ran

    def test_host_lookups_are_cached(self, business: Business) -> None:
        assert domain_lookups(lambda: get("/t/whoami")) == 1
        assert domain_lookups(lambda: get("/t/whoami")) == 0

    def test_unknown_hosts_are_cached_too(self) -> None:
        assert domain_lookups(lambda: get("/t/whoami", host="nobody.localhost")) == 1
        assert domain_lookups(lambda: get("/t/whoami", host="nobody.localhost")) == 0

    def test_cache_expires_after_60_seconds(self, business: Business) -> None:
        with time_machine.travel(datetime(2026, 10, 1, 8, 0, tzinfo=UTC), tick=False) as clock:
            assert domain_lookups(lambda: get("/t/whoami")) == 1
            clock.shift(59)
            assert domain_lookups(lambda: get("/t/whoami")) == 0
            clock.shift(2)
            assert domain_lookups(lambda: get("/t/whoami")) == 1

    def test_health_answers_on_any_host(self) -> None:
        response = get("/api/v1/health", host="nobody.localhost")
        assert response.status_code == 200

    def test_exempt_paths_are_only_the_health_check(self) -> None:
        assert settings.TENANCY_EXEMPT_PATHS == ("/api/v1/health",)

    def test_hosts_outside_allowed_hosts_are_refused(self) -> None:
        response = Client(raise_request_exception=False).get(
            "/t/whoami", headers={"host": "evil.example.com"}
        )
        assert response.status_code == 400


class TestPlatformHost:
    @override_settings(PLATFORM_ADMIN_HOST="admin.localhost")
    def test_api_service_refuses_the_admin_host(self) -> None:
        assert get("/t/whoami", host="admin.localhost").status_code == 404

    @override_settings(PLATFORM_ADMIN_HOST="admin.localhost", DJANGO_SERVICE="platform_admin")
    def test_platform_service_serves_the_admin_host_with_no_business(self) -> None:
        body = get("/t/whoami", host="admin.localhost").json()
        assert body["business_id"] is None
        assert body["db_business_id"] is None

    @override_settings(PLATFORM_ADMIN_HOST="admin.localhost", DJANGO_SERVICE="platform_admin")
    def test_platform_service_refuses_business_hosts(self, business: Business) -> None:
        assert get("/t/whoami").status_code == 404


class TestTransaction:
    def test_request_runs_in_a_transaction_with_the_database_setting(
        self, business: Business
    ) -> None:
        body = get("/t/whoami").json()
        assert body["db_business_id"] == str(business.id)
        assert body["in_transaction"] is True

    def test_setting_is_gone_after_the_response(self, business: Business) -> None:
        get("/t/whoami")
        body = get("/api/v1/health")  # same connection, no business
        assert body.status_code == 200
        with connection.cursor() as cursor:
            cursor.execute("SELECT NULLIF(current_setting('app.business_id', true), '')")
            assert cursor.fetchone() == (None,)

    def test_a_crashing_view_commits_nothing(self, business: Business) -> None:
        response = get("/t/create-then-raise", client=Client(raise_request_exception=False))
        assert response.status_code == 500
        assert response.json()["code"] == "server_error"
        assert widget_names(business) == []

    def test_a_5xx_response_commits_nothing(self, business: Business) -> None:
        assert get("/t/create-then-503").status_code == 503
        assert widget_names(business) == []

    def test_a_returned_4xx_keeps_its_writes(self, business: Business) -> None:
        assert get("/t/create-then-400").status_code == 400
        assert widget_names(business) == ["kept"]


def test_forgetting_a_host_makes_the_next_request_look_it_up_again(business: Business) -> None:
    assert domain_lookups(lambda: get("/t/whoami")) == 1
    forget_host(HOST)
    assert domain_lookups(lambda: get("/t/whoami")) == 1
