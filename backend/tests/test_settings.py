"""The settings refuse unsafe configurations (M1 task T01b)."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.checks import require_postgres, validate_production

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTGRES_URL = "postgres://dial_app:x@localhost:5432/dialaservice"
GOOD_SECRET = "k" * 64


def good_production_settings(**overrides: Any) -> dict[str, Any]:
    settings = {
        "DEBUG": False,
        "SECRET_KEY": GOOD_SECRET,
        "ALLOWED_HOSTS": [".dialaservice.co.ke"],
        "REDIS_URL": "rediss://default:x@redis.example:6379",
    }
    settings.update(overrides)
    return settings


class TestRequirePostgres:
    def test_accepts_postgres(self) -> None:
        require_postgres("django.db.backends.postgresql")

    @pytest.mark.parametrize(
        "engine", ["django.db.backends.sqlite3", "django.db.backends.mysql", ""]
    )
    def test_refuses_anything_else(self, engine: str) -> None:
        with pytest.raises(ImproperlyConfigured, match="PostgreSQL"):
            require_postgres(engine)


class TestValidateProduction:
    def test_accepts_safe_settings(self) -> None:
        validate_production(good_production_settings())

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"DEBUG": True}, "DJANGO_DEBUG"),
            ({"SECRET_KEY": "short"}, "DJANGO_SECRET_KEY"),
            ({"SECRET_KEY": "change-me-to-a-long-random-string" + "x" * 40}, "DJANGO_SECRET_KEY"),
            ({"ALLOWED_HOSTS": []}, "DJANGO_ALLOWED_HOSTS"),
            ({"REDIS_URL": ""}, "REDIS_URL"),
        ],
    )
    def test_refuses_each_unsafe_value(self, overrides: dict[str, Any], message: str) -> None:
        with pytest.raises(ImproperlyConfigured, match=message):
            validate_production(good_production_settings(**overrides))

    def test_reports_every_problem_at_once(self) -> None:
        bad = good_production_settings(DEBUG=True, REDIS_URL="")
        with pytest.raises(ImproperlyConfigured) as excinfo:
            validate_production(bad)
        assert "DJANGO_DEBUG" in str(excinfo.value)
        assert "REDIS_URL" in str(excinfo.value)


def load_settings(module: str, **env: str) -> subprocess.CompletedProcess[str]:
    """Import a settings module in a fresh interpreter with only the given variables."""
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DATABASE"))}
    clean_env.pop("REDIS_URL", None)
    clean_env.update(env)
    clean_env["DJANGO_SETTINGS_MODULE"] = module
    clean_env["DJANGO_READ_DOT_ENV"] = "0"
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND_DIR,
        env=clean_env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestSettingsModules:
    def test_sqlite_database_is_refused(self) -> None:
        result = load_settings(
            "config.settings.test",
            DJANGO_SECRET_KEY=GOOD_SECRET,
            DATABASE_URL="sqlite:///db.sqlite3",
        )
        assert result.returncode != 0
        assert "must point to PostgreSQL" in result.stderr

    def test_production_refuses_placeholder_values(self) -> None:
        result = load_settings(
            "config.settings.production",
            DJANGO_SECRET_KEY="change-me-to-a-long-random-string",
            DATABASE_URL=POSTGRES_URL,
            DJANGO_ALLOWED_HOSTS=".dialaservice.co.ke",
        )
        assert result.returncode != 0
        assert "Unsafe production settings" in result.stderr

    def test_production_starts_with_safe_values(self) -> None:
        result = load_settings(
            "config.settings.production",
            DJANGO_SECRET_KEY=GOOD_SECRET,
            DATABASE_URL=POSTGRES_URL,
            DJANGO_ALLOWED_HOSTS=".dialaservice.co.ke",
            REDIS_URL="redis://localhost:6379/0",
        )
        assert result.returncode == 0, result.stderr
