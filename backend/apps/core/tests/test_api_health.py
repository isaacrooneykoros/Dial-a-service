"""GET /api/v1/health checks the database and Redis (M1 task T03b)."""

from typing import Any

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import override_settings

from apps.core.api import views

pytestmark = pytest.mark.django_db

URL = "/api/v1/health"


def test_healthy_without_redis_in_development(client: Any) -> None:
    with override_settings(REDIS_URL=""):
        response = client.get(URL)
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "not_configured"},
    }


def test_checks_the_cache_when_redis_is_configured(client: Any) -> None:
    with override_settings(REDIS_URL="redis://configured"):
        response = client.get(URL)
    assert response.json()["checks"]["redis"] == "ok"


def test_database_failure_gives_503(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(views, "check_database", lambda: views.ERROR)
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_cache_exception_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(cache, "set", broken)
    with override_settings(REDIS_URL="redis://configured"):
        assert views.check_redis() == views.ERROR


def test_cache_returning_wrong_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "get", lambda key: None)
    with override_settings(REDIS_URL="redis://configured"):
        assert views.check_redis() == views.ERROR


def test_database_exception_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenCursor:
        def __enter__(self) -> "BrokenCursor":
            raise ConnectionError("db down")

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(connection, "cursor", lambda: BrokenCursor())
    assert views.check_database() == views.ERROR


def test_health_only_allows_get(client: Any) -> None:
    response = client.post(URL)
    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
