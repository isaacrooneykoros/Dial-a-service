"""Direct database connections for tests that must act as a specific role.

Most tests use Django's connection, which runs as dial_app. A few need the
owner (to run DDL such as migration operations) or a second, independent
dial_app connection. Both use Neon's direct host.
"""

from typing import Any

import environ
import psycopg
from django.conf import settings

from scripts.db.setup_roles import direct_host


def connect_as(url: str, database: str, *, autocommit: bool = True) -> psycopg.Connection[Any]:
    config = environ.Env.db_url_config(url)
    return psycopg.connect(
        host=direct_host(config["HOST"]),
        port=config.get("PORT") or None,
        user=config["USER"],
        password=config["PASSWORD"],
        dbname=database,
        autocommit=autocommit,
        **config.get("OPTIONS", {}),
    )


def owner_connect(database: str) -> psycopg.Connection[Any]:
    """dial_owner, autocommit: for DDL in tests and for creating the test database."""
    return connect_as(settings.DATABASE_MIGRATION_URL, database)


def platform_connect(database: str) -> psycopg.Connection[Any]:
    """dial_platform (BYPASSRLS), autocommit: for platform-only rows such as platform staff."""
    if not settings.PLATFORM_DATABASE_URL:
        raise RuntimeError(
            "PLATFORM_DATABASE_URL must be set (scripts/db/setup_roles.py writes it)."
        )
    return connect_as(settings.PLATFORM_DATABASE_URL, database)


def app_connect(database: str, *, autocommit: bool = True) -> psycopg.Connection[Any]:
    """A second, independent dial_app connection."""
    return connect_as(settings.DATABASE_APP_URL, database, autocommit=autocommit)
