"""Pure parts of scripts/db/setup_roles.py (M1 task T02a).

The database-facing parts are exercised against Postgres in tests/test_db_roles.py (T02b)
and by running the script against Neon and CI.
"""

from pathlib import Path

import pytest

from scripts.db.setup_roles import (
    direct_host,
    pooled_host,
    role_url,
    split_blocks,
    upsert_env_lines,
)

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "db"


class TestSplitBlocks:
    def test_real_script_has_the_three_role_blocks(self) -> None:
        blocks = split_blocks((SCRIPTS_DIR / "create_roles.sql").read_text(encoding="utf-8"))
        assert set(blocks) == {"owner", "app", "platform"}
        assert "NOBYPASSRLS" in blocks["app"]
        assert "BYPASSRLS" in blocks["platform"]
        assert "NOBYPASSRLS" not in blocks["platform"]

    def test_passwords_are_never_literal_in_the_script(self) -> None:
        script = (SCRIPTS_DIR / "create_roles.sql").read_text(encoding="utf-8")
        assert "PASSWORD '" not in script
        assert script.count("current_setting('dial.") == 5

    def test_preamble_is_ignored(self) -> None:
        assert split_blocks("-- header\n-- @block a\nSELECT 1;\n-- @block b\nSELECT 2;\n") == {
            "a": "SELECT 1;",
            "b": "SELECT 2;",
        }


class TestNeonHosts:
    @pytest.mark.parametrize(
        ("host", "pooled"),
        [
            (
                "ep-cool-dew-123.eu-central-1.aws.neon.tech",
                "ep-cool-dew-123-pooler.eu-central-1.aws.neon.tech",
            ),
            (
                "ep-cool-dew-123-pooler.eu-central-1.aws.neon.tech",
                "ep-cool-dew-123-pooler.eu-central-1.aws.neon.tech",
            ),
            ("localhost", "localhost"),
            ("db.internal", "db.internal"),
        ],
    )
    def test_pooled_host(self, host: str, pooled: str) -> None:
        assert pooled_host(host) == pooled

    def test_direct_host_strips_pooler(self) -> None:
        assert (
            direct_host("ep-cool-dew-123-pooler.eu-central-1.aws.neon.tech")
            == "ep-cool-dew-123.eu-central-1.aws.neon.tech"
        )
        assert direct_host("localhost") == "localhost"


class TestRoleUrl:
    BASE = "postgresql://dial_owner:ownerpw@ep-a-1.eu-central-1.aws.neon.tech/dialaservice?sslmode=require"

    def test_app_url_uses_pooler_and_keeps_database_and_query(self) -> None:
        url = role_url(self.BASE, "dial_app", "pw", pooled=True)
        assert url == (
            "postgresql://dial_app:pw@ep-a-1-pooler.eu-central-1.aws.neon.tech"
            "/dialaservice?sslmode=require"
        )

    def test_platform_url_is_direct(self) -> None:
        url = role_url(self.BASE, "dial_platform", "pw", pooled=False)
        assert "@ep-a-1.eu-central-1.aws.neon.tech/" in url

    def test_password_is_url_encoded_and_port_kept(self) -> None:
        url = role_url("postgres://u:p@localhost:5433/db", "dial_app", "a/b@c:d", pooled=True)
        assert url == "postgres://dial_app:a%2Fb%40c%3Ad@localhost:5433/db"


class TestUpsertEnvLines:
    def test_replaces_existing_and_appends_missing(self) -> None:
        text = "A=1\nDATABASE_URL=old\n# DATABASE_URL=commented\n"
        result = upsert_env_lines(text, {"DATABASE_URL": "new", "PLATFORM_DATABASE_URL": "p"})
        assert (
            result == "A=1\nDATABASE_URL=new\n# DATABASE_URL=commented\nPLATFORM_DATABASE_URL=p\n"
        )

    def test_empty_file(self) -> None:
        assert upsert_env_lines("", {"X": "1"}) == "X=1\n"
