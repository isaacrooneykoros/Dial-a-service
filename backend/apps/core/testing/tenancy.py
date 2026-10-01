"""The cross-business test harness (CLAUDE.md section 6.1, ADR-0001 section 7).

Every endpoint test module (``apps/*/tests/test_api_*.py``) must prove that a
user of business A gets 404 on business B's object; tests/test_endpoint_harness_meta.py
fails if one doesn't call ``assert_cross_business_404``.

    def test_cross_business(business_a, business_b, api_client_for):
        assert_cross_business_404(
            owner=business_b,
            intruder=api_client_for(business_a),
            make_object=lambda: WidgetFactory(),
            url_for=lambda widget: f"/api/v1/widgets/{widget.pk}",
        )

The harness first requests the object as its owner (proving the URL works, and
warming any cache), then as the intruder, who must get the same 404 envelope
as for an object that doesn't exist (X-04: identical for both cases).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business
from apps.tenancy.tests.factories import BusinessDomainFactory

ClientFor = Callable[..., APIClient]


class AppClient(APIClient):
    """Behaves like the apps: every POST carries a fresh Idempotency-Key (CLAUDE.md 6.5),
    unless the test passes its own (``HTTP_IDEMPOTENCY_KEY``) or ``idempotency_key=None``."""

    def post(
        self,
        path: str,
        data: Any = None,
        format: str | None = None,
        *args: Any,
        idempotency_key: str | bool | None = True,
        **extra: Any,
    ) -> Any:
        if idempotency_key is True:
            extra.setdefault("HTTP_IDEMPOTENCY_KEY", uuid.uuid4().hex)
        elif isinstance(idempotency_key, str):
            extra["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
        return super().post(path, data, format, *args, **extra)


def host_of(business: Business) -> str:
    return f"{business.slug}.localhost"


def make_business(slug: str) -> Business:
    domain = BusinessDomainFactory(
        business__slug=slug, business__name=slug.title(), host=f"{slug}.localhost"
    )
    business: Business = domain.business
    return business


@pytest.fixture
def business_a(db: None) -> Business:
    return make_business("business-a")


@pytest.fixture
def business_b(db: None) -> Business:
    return make_business("business-b")


@pytest.fixture
def api_client_for() -> ClientFor:
    """``api_client_for(business, user=None)``: a client on that business's host.

    ``user`` is accepted for the authenticated endpoints added from T05b on.
    """

    def build(business: Business, user: Any = None) -> APIClient:
        client = AppClient(headers={"host": host_of(business)}, raise_request_exception=False)
        if user is not None:
            client.force_authenticate(user)
        return client

    return build


def assert_cross_business_404[T](
    *,
    owner: Business,
    intruder: APIClient,
    make_object: Callable[[], T],
    url_for: Callable[[T], str],
    method: str = "get",
    owner_client: APIClient | None = None,
    data: Any = None,
    expected_owner_status: int | None = None,
) -> None:
    """``intruder`` (another business's client) gets a 404 envelope on ``owner``'s object."""
    with tenant_context(owner.id):
        obj = make_object()
    url = url_for(obj)

    owner_client = owner_client or AppClient(
        headers={"host": host_of(owner)}, raise_request_exception=False
    )
    owner_response = getattr(owner_client, method)(url, data=data, format="json")
    expected: tuple[int, ...] = (
        (200, 201, 204) if expected_owner_status is None else (expected_owner_status,)
    )
    assert owner_response.status_code in expected, (
        f"The owner can't reach {url} ({owner_response.status_code}); "
        "the cross-business check would prove nothing."
    )

    response = getattr(intruder, method)(url, data=data, format="json")
    assert response.status_code == 404, (
        f"Business data leaked: {method.upper()} {url} returned {response.status_code} "
        f"to another business: {response.content[:200]!r}"
    )
    body = response.json()
    assert body["code"] == "not_found", body
    cache.clear()
