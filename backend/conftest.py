"""Project-wide pytest fixtures.

Test database roles (ADR-0001 section 7): the test database is created and
migrated as dial_owner, exactly like production, so tables are owned by the
owner and row-level security is forced. Every test then runs as dial_app, the
role the API uses, so RLS is really exercised.

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
from django.test.utils import setup_databases, teardown_databases

from scripts.db.setup_roles import direct_host

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

    with django_db_blocker.unblock():
        _use(owner)
        old_config = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            keepdb=django_db_keepdb,
        )
        with connections["default"].cursor() as cursor:
            cursor.execute(GRANTS_SQL.read_text(encoding="utf-8"))
        _use(app)

    yield

    with django_db_blocker.unblock():
        _use(owner)
        if not django_db_keepdb:
            teardown_databases(old_config, verbosity=request.config.option.verbose)
