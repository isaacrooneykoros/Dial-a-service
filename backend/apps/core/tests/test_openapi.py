"""The committed OpenAPI schema matches the code, and pagination defaults hold (M1 task T03b)."""

from pathlib import Path

import pytest
from django.core.management import CommandError, call_command
from rest_framework.settings import api_settings

from apps.core.api.pagination import DefaultCursorPagination
from apps.core.management.commands import check_openapi


def test_committed_schema_is_up_to_date() -> None:
    call_command("check_openapi")


def test_stale_schema_fails_with_a_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stale = tmp_path / "openapi.yaml"
    stale.write_text("openapi: 3.0.3\n", encoding="utf-8")
    monkeypatch.setattr(check_openapi, "SCHEMA_FILE", stale)
    with pytest.raises(CommandError, match="out of date"):
        call_command("check_openapi")


def test_write_regenerates_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "openapi.yaml"
    monkeypatch.setattr(check_openapi, "SCHEMA_FILE", target)
    call_command("check_openapi", "--write")
    assert "/api/v1/health" in target.read_text(encoding="utf-8")
    call_command("check_openapi")


def test_cursor_pagination_is_the_default_with_20_per_page() -> None:
    assert api_settings.DEFAULT_PAGINATION_CLASS is DefaultCursorPagination
    assert DefaultCursorPagination.page_size == 20
    assert DefaultCursorPagination.max_page_size == 100
