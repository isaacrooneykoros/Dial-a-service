"""Database-level isolation: raw SQL as dial_app never sees another business (M1 T04d).

Layer 2 on its own: these queries bypass Django's managers entirely. Every
tenant table is seeded for two businesses with its factory, then queried with
plain SQL under each context.
"""

import importlib
from typing import Any

import pytest
from django.apps import apps
from django.db import DatabaseError, connection, models, transaction
from psycopg import sql as psql

from apps.core.models import TenantModel
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business
from apps.tenancy.tests.factories import BusinessFactory

pytestmark = pytest.mark.django_db


def tenant_models() -> list[type[TenantModel]]:
    return [
        model
        for model in apps.get_models()
        if issubclass(model, TenantModel) and model._meta.managed
    ]


def factory_for(model: type[models.Model]) -> Any:
    """By convention <app>.tests.factories.<Model>Factory (tests.testapp.factories here)."""
    package = model.__module__.rsplit(".", 1)[0]
    module_name = (
        f"{package}.factories" if package.startswith("tests.") else f"{package}.tests.factories"
    )
    module = importlib.import_module(module_name)
    return getattr(module, f"{model.__name__}Factory")


def run(query: psql.Composable | str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(
            query.as_string(cursor.cursor) if isinstance(query, psql.Composable) else query, params
        )
        return list(cursor.fetchall()) if cursor.description else []


def set_business(business_id: object) -> None:
    run("SELECT set_config('app.business_id', %s, true)", [str(business_id) if business_id else ""])


def move_all_rows(table: psql.Identifier, *, to: object) -> None:
    """Try to reassign every visible row; contained in a savepoint so the test can go on."""
    with transaction.atomic():
        run(psql.SQL("UPDATE {} SET business_id = %s").format(table), [to])


@pytest.fixture
def seeded() -> tuple[Business, Business]:
    a, b = BusinessFactory(), BusinessFactory()
    for business in (a, b):
        with tenant_context(business.id):
            for model in tenant_models():
                factory_for(model)()
    return a, b


def test_every_tenant_model_has_a_factory() -> None:
    missing = []
    for model in tenant_models():
        try:
            factory_for(model)
        except (ImportError, AttributeError):
            missing.append(model._meta.label)
    assert not missing, f"Add a factory for each tenant model: {missing}"


def test_raw_sql_under_a_sees_none_of_b(seeded: tuple[Business, Business]) -> None:
    a, b = seeded
    set_business(a.id)
    for model in tenant_models():
        table = psql.Identifier(model._meta.db_table)
        rows = run(psql.SQL("SELECT business_id FROM {}").format(table))
        assert rows, f"{model._meta.db_table}: business A should see its own rows"
        assert {row[0] for row in rows} == {a.id}, f"{model._meta.db_table} leaked rows"
        count_b = run(
            psql.SQL("SELECT count(*) FROM {} WHERE business_id = %s").format(table), [b.id]
        )
        assert count_b == [(0,)], f"{model._meta.db_table}: business B's rows are visible"


def test_raw_sql_with_no_business_sees_nothing(seeded: tuple[Business, Business]) -> None:
    for value in (None, ""):
        set_business(value)
        for model in tenant_models():
            table = psql.Identifier(model._meta.db_table)
            assert run(psql.SQL("SELECT count(*) FROM {}").format(table)) == [(0,)]


def test_rows_cannot_be_moved_or_written_into_another_business(
    seeded: tuple[Business, Business],
) -> None:
    a, b = seeded
    for model in tenant_models():
        table = psql.Identifier(model._meta.db_table)
        set_business(a.id)
        with pytest.raises(DatabaseError, match="row-level security"):
            move_all_rows(table, to=b.id)


def test_b_rows_cannot_be_updated_or_deleted_from_a(seeded: tuple[Business, Business]) -> None:
    a, b = seeded
    set_business(a.id)
    for model in tenant_models():
        table = psql.Identifier(model._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                psql.SQL("DELETE FROM {} WHERE business_id = %s")
                .format(table)
                .as_string(cursor.cursor),
                [b.id],
            )
            assert cursor.rowcount == 0, f"{model._meta.db_table}: deleted B's rows from A"
    set_business(b.id)
    for model in tenant_models():
        table = psql.Identifier(model._meta.db_table)
        assert run(psql.SQL("SELECT count(*) FROM {}").format(table)) == [(1,)]
