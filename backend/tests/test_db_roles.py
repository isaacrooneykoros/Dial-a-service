"""Tests run as dial_app on a database owned by dial_owner (M1 T02b, ADR-0001 section 7)."""

import pytest
from django.db import DatabaseError, connection, transaction

pytestmark = pytest.mark.django_db


def fetch_one(query: str) -> tuple[object, ...]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()
    assert row is not None
    return tuple(row)


def test_tests_connect_as_dial_app() -> None:
    assert fetch_one("SELECT current_user") == ("dial_app",)


def test_test_database_is_separate() -> None:
    (name,) = fetch_one("SELECT current_database()")
    assert str(name).startswith("test_")


def test_dial_app_cannot_bypass_row_level_security() -> None:
    assert fetch_one(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    ) == (False, False)


def test_dial_app_cannot_become_a_role_that_bypasses_rls() -> None:
    (count,) = fetch_one(
        "SELECT count(*) FROM pg_roles r WHERE (r.rolsuper OR r.rolbypassrls) "
        "AND pg_has_role(current_user, r.oid, 'MEMBER')"
    )
    assert count == 0


def test_tables_are_owned_by_dial_owner() -> None:
    (owner,) = fetch_one("SELECT tableowner FROM pg_tables WHERE tablename = 'django_migrations'")
    assert owner == "dial_owner"


def test_dial_app_cannot_create_tables() -> None:
    with (
        pytest.raises(DatabaseError, match="permission denied"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("CREATE TABLE should_not_exist (id int)")


def test_dial_app_can_read_and_write_rows() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO django_content_type (app_label, model) VALUES ('probe', 'probe')"
        )
        cursor.execute("SELECT count(*) FROM django_content_type WHERE app_label = 'probe'")
        assert cursor.fetchone() == (1,)
