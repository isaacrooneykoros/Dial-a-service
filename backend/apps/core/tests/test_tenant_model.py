"""TenantModel's manager and save() guard: layer 1 of isolation (M1 T04a, ADR-0001 section 3).

Row-level security (layer 2) is added to tenant tables in T04b; these tests
check the application layer on its own.
"""

import pytest

from apps.core.tenant_context import TenantContextMissing, TenantMismatch, tenant_context
from apps.tenancy.models import Business
from apps.tenancy.tests.factories import BusinessFactory
from tests.testapp.models import Widget

pytestmark = pytest.mark.django_db


@pytest.fixture
def a() -> Business:
    return BusinessFactory()


@pytest.fixture
def b() -> Business:
    return BusinessFactory()


def test_querying_without_a_business_raises() -> None:
    with pytest.raises(TenantContextMissing):
        Widget.objects.all()


def test_saving_without_a_business_raises(a: Business) -> None:
    with pytest.raises(TenantContextMissing):
        Widget(name="orphan").save()


def test_create_fills_the_business_from_context(a: Business) -> None:
    with tenant_context(a.id):
        widget = Widget.objects.create(name="tag printer")
    assert widget.business_id == a.id


def test_queries_see_only_the_current_business(a: Business, b: Business) -> None:
    with tenant_context(a.id):
        Widget.objects.create(name="a1")
        Widget.objects.create(name="a2")
    with tenant_context(b.id):
        Widget.objects.create(name="b1")
        assert list(Widget.objects.values_list("name", flat=True)) == ["b1"]
    with tenant_context(a.id):
        assert sorted(Widget.objects.values_list("name", flat=True)) == ["a1", "a2"]


def test_saving_a_row_for_another_business_is_refused(a: Business, b: Business) -> None:
    with tenant_context(a.id):
        widget = Widget.objects.create(name="a1")
    widget.name = "stolen"
    with tenant_context(b.id), pytest.raises(TenantMismatch):
        widget.save()


def test_bulk_create_fills_and_guards_the_business(a: Business, b: Business) -> None:
    with tenant_context(a.id):
        created = Widget.objects.bulk_create([Widget(name="x"), Widget(name="y")])
        assert {w.business_id for w in created} == {a.id}
        with pytest.raises(TenantMismatch):
            Widget.objects.bulk_create([Widget(name="z", business_id=b.id)])


def test_unscoped_manager_sees_every_business(a: Business, b: Business) -> None:
    for business in (a, b):
        with tenant_context(business.id):
            Widget.objects.create(name="w")
    assert Widget.unscoped.count() == 2  # platform-scope: test of the platform manager


def test_business_field_is_not_editable() -> None:
    assert not Widget._meta.get_field("business").editable


def test_business_has_no_reverse_accessor_to_tenant_rows() -> None:
    accessors = {rel.get_accessor_name() for rel in Business._meta.related_objects}
    assert "widget_set" not in accessors
    assert not hasattr(Business, "widget_set")


def test_resaving_a_row_in_its_own_business_works(a: Business) -> None:
    with tenant_context(a.id):
        widget = Widget.objects.create(name="old")
        widget.name = "new"
        widget.save()
        assert Widget.objects.get().name == "new"
