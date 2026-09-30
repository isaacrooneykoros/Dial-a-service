"""Guards that stop the project starting with unsafe settings.

Kept free of Django imports so the settings modules can call them while loading,
and so tests can call them directly.
"""

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ImproperlyConfigured

POSTGRES_ENGINE = "django.db.backends.postgresql"

# Placeholder values from .env.example that must never reach production.
_PLACEHOLDER_MARKERS = ("change-me", "dummy", "example", "insecure")


def require_postgres(engine: str) -> None:
    """Row-level security can't be tested or enforced on anything but Postgres."""
    if engine != POSTGRES_ENGINE:
        raise ImproperlyConfigured(
            f"DATABASE_URL must point to PostgreSQL (got engine {engine!r}). "
            "SQLite and other databases are not supported."
        )


def validate_production(settings: Mapping[str, Any]) -> None:
    """Refuse to start production with debug on, placeholder secrets or missing services."""
    problems: list[str] = []

    if settings["DEBUG"]:
        problems.append("DJANGO_DEBUG must be false.")

    secret = settings["SECRET_KEY"]
    if len(secret) < 50 or any(marker in secret.lower() for marker in _PLACEHOLDER_MARKERS):
        problems.append("DJANGO_SECRET_KEY must be a real random value of at least 50 characters.")

    if not settings["ALLOWED_HOSTS"]:
        problems.append("DJANGO_ALLOWED_HOSTS must be set.")

    if not settings["REDIS_URL"]:
        problems.append("REDIS_URL must be set: tasks must never run inline in production.")

    if problems:
        raise ImproperlyConfigured("Unsafe production settings: " + " ".join(problems))
