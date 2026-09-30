"""Create the database roles and grants, then verify them (M1 task T02a, ADR-0001 section 5).

Usage, from backend/ with the virtualenv active:

    python -m scripts.db.setup_roles              # Neon: connect as dial_owner, write .env
    python -m scripts.db.setup_roles --verify-only
    python -m scripts.db.setup_roles --admin-url postgres://postgres:...@localhost/postgres \\
        --create-database dialaservice            # CI or local Postgres, as a superuser

Passwords for dial_app and dial_platform come from DIAL_APP_PASSWORD and
DIAL_PLATFORM_PASSWORD when set (CI); otherwise fresh ones are generated and
written into backend/.env as DATABASE_URL and PLATFORM_DATABASE_URL. Passwords
are never printed.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import environ
import psycopg
from psycopg import sql

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"

BLOCK_MARKER = re.compile(r"^-- @block (\w+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


# --- Pure helpers (unit-tested) --------------------------------------------------


def split_blocks(script: str) -> dict[str, str]:
    """Split create_roles.sql into its named ``-- @block`` sections."""
    parts = BLOCK_MARKER.split(script)
    # parts = [preamble, name1, body1, name2, body2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def pooled_host(host: str) -> str:
    """Neon's pooled host adds -pooler to the endpoint label; other hosts are unchanged."""
    if not host.endswith(".neon.tech"):
        return host
    label, _, rest = host.partition(".")
    if label.endswith("-pooler"):
        return host
    return f"{label}-pooler.{rest}"


def direct_host(host: str) -> str:
    """The direct (unpooled) form of a Neon host."""
    label, _, rest = host.partition(".")
    return f"{label.removesuffix('-pooler')}.{rest}" if rest else host


def role_url(base_url: str, user: str, password: str, *, pooled: bool) -> str:
    """Build a connection URL for another role on the same database as ``base_url``."""
    parts = urlsplit(base_url)
    host = parts.hostname or ""
    host = pooled_host(host) if pooled else direct_host(host)
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def upsert_env_lines(text: str, values: dict[str, str]) -> str:
    """Replace ``KEY=...`` lines in a .env text, appending keys that are missing."""
    lines = text.splitlines()
    seen: set[str] = set()
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values and not line.lstrip().startswith("#"):
            lines[index] = f"{key}={values[key]}"
            seen.add(key)
    lines.extend(f"{key}={value}" for key, value in values.items() if key not in seen)
    return "\n".join(lines) + "\n"


# --- Database work ------------------------------------------------------------------


def set_passwords(conn: psycopg.Connection, passwords: dict[str, str]) -> None:
    # Session-level settings on this one-off admin connection (direct host, not the
    # pooler), read by the DO blocks in create_roles.sql. The application itself
    # never uses session-level settings (CLAUDE.md section 6.1).
    for name, value in passwords.items():
        conn.execute("SELECT set_config(%s, %s, false)", (f"dial.{name}_password", value))


def create_roles(conn: psycopg.Connection, *, create_owner: bool) -> list[Check]:
    blocks = split_blocks((SCRIPTS_DIR / "create_roles.sql").read_text(encoding="utf-8"))
    results: list[Check] = []
    for name in ("owner", "app", "platform"):
        if name == "owner" and not create_owner:
            continue
        try:
            conn.execute(sql.SQL(blocks[name]))
            results.append(Check(f"role {name}", True))
        except psycopg.Error as exc:
            results.append(Check(f"role {name}", False, exc.diag.message_primary or str(exc)))
    return results


def grant_privileges(conn: psycopg.Connection) -> None:
    script = (SCRIPTS_DIR / "grant_privileges.sql").read_text(encoding="utf-8")
    conn.execute(sql.SQL(script))


def verify(conn: psycopg.Connection) -> list[Check]:
    def one(query: str) -> object:
        row = conn.execute(query).fetchone()
        return row[0] if row else None

    app = conn.execute(
        "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles "
        "WHERE rolname = 'dial_app'"
    ).fetchone()
    platform_bypass = one("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'dial_platform'")
    bypass_paths = [
        r[0]
        for r in conn.execute(
            "SELECT rolname FROM pg_roles r WHERE (r.rolsuper OR r.rolbypassrls) "
            "AND pg_has_role('dial_app', r.oid, 'MEMBER')"
        ).fetchall()
    ]
    return [
        Check("dial_app exists", app is not None),
        Check(
            "dial_app is not superuser and cannot bypass RLS",
            app is not None and not app[0] and not app[1],
        ),
        Check(
            "dial_app cannot create roles or databases",
            app is not None and not app[2] and not app[3],
        ),
        Check(
            "dial_app cannot become any role that bypasses RLS",
            not bypass_paths,
            ", ".join(bypass_paths),
        ),
        Check(
            "dial_app cannot create objects in schema public",
            one("SELECT has_schema_privilege('dial_app', 'public', 'CREATE')") is False,
        ),
        Check(
            "dial_app owns no tables",
            one("SELECT count(*) FROM pg_tables WHERE tableowner = 'dial_app'") == 0,
        ),
        Check("dial_platform exists with BYPASSRLS", platform_bypass is True),
    ]


# --- Command line -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else "")
    parser.add_argument(
        "--admin-url", help="Connect with this URL instead of DATABASE_MIGRATION_URL"
    )
    parser.add_argument("--create-database", help="Create this database owned by dial_owner (CI)")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--grants-only", action="store_true", help="Only re-apply grants (after migrations)"
    )
    parser.add_argument("--no-write-env", action="store_true", help="Don't touch backend/.env")
    args = parser.parse_args(argv)

    env = environ.Env()
    if ENV_FILE.exists():
        environ.Env.read_env(ENV_FILE)
    admin_url = args.admin_url or env("DATABASE_MIGRATION_URL", default="")
    if not admin_url or "dummy-password" in admin_url:
        sys.stderr.write(
            "DATABASE_MIGRATION_URL is not set in backend/.env. See docs/ops/neon-dev.md step 5.\n"
        )
        return 2

    if args.grants_only:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            grant_privileges(conn)
        sys.stdout.write("[OK  ] grants in this database\n")
        return 0

    passwords = {
        "app": os.environ.get("DIAL_APP_PASSWORD") or secrets.token_urlsafe(32),
        "platform": os.environ.get("DIAL_PLATFORM_PASSWORD") or secrets.token_urlsafe(32),
        "owner": os.environ.get("DIAL_OWNER_PASSWORD") or secrets.token_urlsafe(32),
    }
    target_url = admin_url
    results: list[Check] = []

    with psycopg.connect(admin_url, autocommit=True) as conn:
        if not args.verify_only:
            set_passwords(conn, passwords)
            results += create_roles(conn, create_owner=bool(args.create_database))
            if args.create_database:
                exists = conn.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (args.create_database,)
                ).fetchone()
                if not exists:
                    conn.execute(
                        sql.SQL("CREATE DATABASE {} OWNER dial_owner").format(
                            sql.Identifier(args.create_database)
                        )
                    )
                target_url = urlunsplit(
                    urlsplit(admin_url)._replace(path=f"/{args.create_database}")
                )

    with psycopg.connect(target_url, autocommit=True) as conn:
        if not args.verify_only:
            grant_privileges(conn)
            results.append(Check("grants in this database", True))
        results += verify(conn)

    for check in results:
        mark = "OK  " if check.ok else "FAIL"
        suffix = f" ({check.detail})" if check.detail else ""
        sys.stdout.write(f"[{mark}] {check.name}{suffix}\n")

    app_created = any(c.name == "role app" and c.ok for c in results)
    if app_created and not args.no_write_env and not os.environ.get("DIAL_APP_PASSWORD"):
        values = {"DATABASE_URL": role_url(target_url, "dial_app", passwords["app"], pooled=True)}
        if any(c.name == "role platform" and c.ok for c in results):
            values["PLATFORM_DATABASE_URL"] = role_url(
                target_url, "dial_platform", passwords["platform"], pooled=False
            )
        text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
        ENV_FILE.write_text(upsert_env_lines(text, values), encoding="utf-8")
        sys.stdout.write(f"Wrote {', '.join(values)} to backend/.env (passwords not shown).\n")

    return 0 if all(c.ok for c in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
