"""EnableTenantRLS and MakeAppendOnly run forwards and backwards (M1 T04b, ADR-0001 section 4).

The SQL is collected from Django's schema editor and run as dial_owner on the
test app's widget table, then put back. dial_app is checked over a second,
independent connection, so these tests don't depend on Django's test transaction.
"""

from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.base import Operation

from apps.core.db import EnableTenantRLS, MakeAppendOnly
from apps.core.testing.database import app_connect, owner_connect

TABLE = "testapp_widget"

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_db(django_db_setup: None, django_db_blocker: Any) -> str:
    name: str = connection.settings_dict["NAME"]
    return name


def collect_sql(operation: Operation, *, backwards: bool = False) -> list[str]:
    state = MigrationLoader(None, ignore_no_migrations=True).project_state(
        ("testapp", "0002_rls_widget")
    )
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        run = operation.database_backwards if backwards else operation.database_forwards
        run("testapp", editor, state, state)
    return [statement.rstrip(";") for statement in editor.collected_sql]


def run_as_owner(database: str, statements: list[str]) -> None:
    with owner_connect(database) as conn:
        for statement in statements:
            conn.execute(statement)


def rls_state(database: str) -> tuple[bool, bool, int]:
    with owner_connect(database) as conn:
        flags = conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            (TABLE,),
        ).fetchone()
        policies = conn.execute(
            "SELECT count(*) FROM pg_policies WHERE tablename = %s", (TABLE,)
        ).fetchone()
    assert flags is not None
    assert policies is not None
    return bool(flags[0]), bool(flags[1]), int(policies[0])


@pytest.fixture
def restore(test_db: str) -> Iterator[Callable[[list[str]], None]]:
    """Register SQL that puts the table back, run even if the test fails."""
    pending: list[list[str]] = []
    yield pending.append
    for statements in reversed(pending):
        run_as_owner(test_db, statements)


def test_enable_tenant_rls_round_trip(test_db: str) -> None:
    operation = EnableTenantRLS("widget")
    assert rls_state(test_db) == (True, True, 1)

    run_as_owner(test_db, collect_sql(operation, backwards=True))
    try:
        assert rls_state(test_db) == (False, False, 0)
    finally:
        run_as_owner(test_db, collect_sql(operation))
    assert rls_state(test_db) == (True, True, 1)


def test_make_append_only_blocks_update_and_delete_for_dial_app(
    test_db: str, restore: Callable[[list[str]], None]
) -> None:
    operation = MakeAppendOnly("widget")
    restore(collect_sql(operation, backwards=True))
    run_as_owner(test_db, collect_sql(operation))

    with app_connect(test_db, autocommit=False) as conn:
        conn.execute("SELECT set_config('app.business_id', gen_random_uuid()::text, true)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(f"UPDATE {TABLE} SET name = 'x'")  # noqa: S608 - fixed table name
        conn.rollback()
        conn.execute("SELECT set_config('app.business_id', gen_random_uuid()::text, true)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(f"DELETE FROM {TABLE}")  # noqa: S608 - fixed table name
        conn.rollback()


def test_operations_describe_and_deconstruct() -> None:
    for operation_class, fragment in ((EnableTenantRLS, "rls"), (MakeAppendOnly, "append_only")):
        operation = operation_class("Widget")
        assert operation.deconstruct() == (operation_class.__name__, ["widget"], {})
        assert operation.migration_name_fragment == f"{fragment}_widget"
        assert "widget" in operation.describe()
        operation.state_forwards("testapp", None)  # type: ignore[arg-type]
