"""Project-wide pytest fixtures.

Test database roles (ADR-0001 section 7): the test database is created and
migrated as dial_owner, exactly like production, so tables are owned by the
owner and row-level security is forced. Every test then runs as dial_app, the
role the API uses, so RLS is really exercised.

Order matters, as in production: the database is created and its default
privileges are set *before* any migration, so every table gets the app grants
from the default privileges and no blanket grant can undo MakeAppendOnly.

Tests connect to Neon's direct host (not the pooler): pooled server connections
would outlive the test run and stop the test database from being dropped.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import environ
import pytest
from django.conf import settings
from django.db import connections
from django.test.utils import setup_databases
from psycopg import sql

from apps.core.testing.database import owner_connect
from scripts.db.setup_roles import direct_host

# The cross-business harness fixtures (business_a, business_b, api_client_for).
pytest_plugins = ["apps.core.testing.tenancy"]

GRANTS_SQL = Path(__file__).resolve().parent / "scripts" / "db" / "grant_privileges.sql"
CREDENTIAL_KEYS = ("USER", "PASSWORD", "HOST", "PORT", "OPTIONS")


def _credentials(url: str) -> dict[str, Any]:
    config = environ.Env.db_url_config(url)
    config["HOST"] = direct_host(config["HOST"])
    return {key: config.get(key, "") for key in CREDENTIAL_KEYS}


def _use(credentials: dict[str, Any]) -> None:
    """Point the default connection at another role, keeping the database name."""
    connection = connections["default"]
    connection.close()
    for key, value in credentials.items():
        if key == "OPTIONS":
            connection.settings_dict["OPTIONS"] = {**connection.settings_dict["OPTIONS"], **value}
        else:
            connection.settings_dict[key] = value


def _prepare_test_database(main_db: str, test_db: str, *, keep: bool) -> None:
    """Create the test database (fresh unless keeping it) and set its privileges."""
    with owner_connect(main_db) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_db,)).fetchone()
        if exists and not keep:
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(test_db)))
            exists = None
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_db)))
    with owner_connect(test_db) as conn:
        conn.execute(GRANTS_SQL.read_text(encoding="utf-8"))
        # Test database only: transactional tests (django_db(transaction=True))
        # empty every table afterwards with TRUNCATE, which dial_app is never
        # granted in real databases.
        conn.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE dial_owner IN SCHEMA public "
            "GRANT TRUNCATE ON TABLES TO dial_app"
        )


def _drop_test_database(main_db: str, test_db: str) -> None:
    with owner_connect(main_db) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(test_db)))


@pytest.fixture(scope="session")
def django_db_setup(
    request: pytest.FixtureRequest,
    django_test_environment: None,
    django_db_blocker: Any,
    django_db_keepdb: bool,
) -> Iterator[None]:
    if not settings.DATABASE_MIGRATION_URL:
        pytest.exit("DATABASE_MIGRATION_URL must be set: tests migrate as dial_owner.", 2)

    app = _credentials(settings.DATABASE_APP_URL)
    owner = _credentials(settings.DATABASE_MIGRATION_URL)
    connection = connections["default"]
    main_db = connection.settings_dict["NAME"]
    test_db = connection.settings_dict.get("TEST", {}).get("NAME") or f"test_{main_db}"

    with django_db_blocker.unblock():
        _prepare_test_database(main_db, test_db, keep=django_db_keepdb)
        _use(owner)
        # keepdb=True: Django reuses the database just prepared and migrates it.
        setup_databases(verbosity=request.config.option.verbose, interactive=False, keepdb=True)
        _use(app)

    yield

    with django_db_blocker.unblock():
        _use(owner)
        connection.settings_dict["NAME"] = main_db
        connection.close()
        if not django_db_keepdb:
            _drop_test_database(main_db, test_db)
