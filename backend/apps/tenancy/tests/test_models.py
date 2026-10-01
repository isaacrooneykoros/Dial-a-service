"""Business and BusinessDomain rules (M1 T04a)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.tenancy.models import Business
from apps.tenancy.tests.factories import BusinessDomainFactory, BusinessFactory
from apps.tenancy.validators import normalize_host, validate_business_slug, validate_host


class TestSlug:
    @pytest.mark.parametrize("slug", ["mamasafi", "clean-pro", "a", "laundry24", "x" * 63])
    def test_valid(self, slug: str) -> None:
        validate_business_slug(slug)

    @pytest.mark.parametrize(
        "slug",
        [
            "MamaSafi",
            "-start",
            "end-",
            "has space",
            "under_score",
            "dot.ted",
            "",
            "x" * 64,
            "mamaé",
        ],
    )
    def test_invalid(self, slug: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            validate_business_slug(slug)
        assert excinfo.value.code == "invalid_slug"

    @pytest.mark.parametrize("slug", ["www", "admin", "api", "app", "console", "staff", "rider"])
    def test_reserved_words_from_w03(self, slug: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            validate_business_slug(slug)
        assert excinfo.value.code == "reserved_slug"


class TestHost:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("mamasafi.localhost:5173", "mamasafi.localhost"),
            ("MamaSafi.DialAService.co.ke", "mamasafi.dialaservice.co.ke"),
            ("mamasafi.dialaservice.co.ke.", "mamasafi.dialaservice.co.ke"),
            ("  cleanpro.localhost ", "cleanpro.localhost"),
            ("[::1]:8000", "[::1]:8000"),
        ],
    )
    def test_normalize(self, raw: str, expected: str) -> None:
        assert normalize_host(raw) == expected

    @pytest.mark.parametrize("host", ["mamasafi.localhost", "a.b.co.ke", "localhost"])
    def test_valid(self, host: str) -> None:
        validate_host(host)

    @pytest.mark.parametrize("host", ["Upper.localhost", "has space.ke", "-bad.ke", "a..b", ""])
    def test_invalid(self, host: str) -> None:
        with pytest.raises(ValidationError):
            validate_host(host)


@pytest.mark.django_db
class TestDatabaseRules:
    def test_defaults(self) -> None:
        business = BusinessFactory()
        assert business.status == Business.Status.TRIAL
        assert (business.country, business.currency, business.timezone) == (
            "KE",
            "KES",
            "Africa/Nairobi",
        )

    def test_slug_is_unique(self) -> None:
        BusinessFactory(slug="mamasafi")
        with pytest.raises(IntegrityError):
            BusinessFactory(slug="mamasafi")

    def test_database_refuses_a_badly_formed_slug(self) -> None:
        with pytest.raises(IntegrityError):
            BusinessFactory(slug="Bad Slug")

    def test_host_is_unique(self) -> None:
        BusinessDomainFactory(host="mamasafi.localhost")
        with pytest.raises(IntegrityError):
            BusinessDomainFactory(host="mamasafi.localhost")

    def test_host_must_be_lowercase(self) -> None:
        with pytest.raises(IntegrityError):
            BusinessDomainFactory(host="MamaSafi.localhost")

    def test_one_primary_domain_per_business(self) -> None:
        domain = BusinessDomainFactory()
        BusinessDomainFactory(business=domain.business, host="old.localhost", is_primary=False)
        with pytest.raises(IntegrityError):
            BusinessDomainFactory(business=domain.business, host="second.localhost")

    def test_readable_names(self) -> None:
        domain = BusinessDomainFactory(business__name="Mama Safi", business__slug="mamasafi")
        assert str(domain.business) == "Mama Safi (mamasafi)"
        assert str(domain) == "mamasafi.localhost"
