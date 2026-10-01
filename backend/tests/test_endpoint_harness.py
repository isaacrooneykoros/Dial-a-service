"""The cross-business harness catches leaks and is used by every endpoint module (M1 T04d)."""

from pathlib import Path

import pytest
from django.core.cache import cache

from apps.core.testing.tenancy import ClientFor, assert_cross_business_404
from apps.tenancy.models import Business
from tests.testapp.factories import WidgetFactory

BACKEND = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.urls("tests.testapp.urls")


@pytest.mark.django_db
def test_a_correctly_scoped_view_passes(
    business_a: Business, business_b: Business, api_client_for: ClientFor
) -> None:
    assert_cross_business_404(
        owner=business_b,
        intruder=api_client_for(business_a),
        make_object=WidgetFactory,
        url_for=lambda widget: f"/t/widgets/{widget.pk}",
    )


@pytest.mark.django_db
def test_a_leak_that_rls_cannot_stop_is_caught(
    business_a: Business, business_b: Business, api_client_for: ClientFor
) -> None:
    """A cache keyed without the business leaks B's widget to A; the harness fails."""
    with pytest.raises(AssertionError, match="Business data leaked"):
        assert_cross_business_404(
            owner=business_b,
            intruder=api_client_for(business_a),
            make_object=WidgetFactory,
            url_for=lambda widget: f"/t/leaky-widgets/{widget.pk}",
        )
    cache.clear()


@pytest.mark.django_db
def test_a_url_the_owner_cannot_reach_proves_nothing(
    business_a: Business, business_b: Business, api_client_for: ClientFor
) -> None:
    with pytest.raises(AssertionError, match="owner can't reach"):
        assert_cross_business_404(
            owner=business_b,
            intruder=api_client_for(business_a),
            make_object=WidgetFactory,
            url_for=lambda widget: "/t/no-such-url",
        )


def test_every_endpoint_test_module_uses_the_harness() -> None:
    """CLAUDE.md section 6.1: every endpoint test module has a cross-business test."""
    modules = sorted(BACKEND.glob("apps/*/tests/test_api_*.py"))
    missing = [
        str(path.relative_to(BACKEND))
        for path in modules
        if "assert_cross_business_404" not in path.read_text(encoding="utf-8")
    ]
    assert not missing, "Add a cross-business test (assert_cross_business_404) to:\n" + "\n".join(
        missing
    )
