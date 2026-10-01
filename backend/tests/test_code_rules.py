"""Repository-wide code rules that linters can't express (CLAUDE.md section 6.1)."""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("apps", "config", "tests")
THIS_FILE = Path(__file__).resolve()


def python_files() -> list[Path]:
    return [
        path
        for directory in SOURCE_DIRS
        for path in (BACKEND / directory).rglob("*.py")
        if "migrations" not in path.parts and path.resolve() != THIS_FILE
    ]


def test_unscoped_manager_is_always_marked_platform_scope() -> None:
    """Every `.unscoped` use carries `# platform-scope: <reason>` on the same line."""
    definition = BACKEND / "apps" / "core" / "models.py"
    offenders = []
    for path in python_files():
        if path == definition:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ".unscoped" in line and not re.search(r"#\s*platform-scope:\s*\S", line):
                offenders.append(f"{path.relative_to(BACKEND)}:{number}: {line.strip()}")
    assert not offenders, "Mark platform-only queries:\n" + "\n".join(offenders)


def test_no_session_level_settings() -> None:
    """The business setting is always transaction-local: set_config(..., true).

    Session-level SET would leak to the next user of a pooled connection
    (CLAUDE.md section 6.1). scripts/ is excluded: its one-off admin connection
    sets role passwords at session level, never the business.
    """
    pattern = re.compile(r"\bSET\s+(SESSION\s+)?app\.|set_config\([^)]*app\.business_id[^)]*false")
    offenders = [
        f"{path.relative_to(BACKEND)}:{number}"
        for path in python_files()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert not offenders, "\n".join(offenders)


def test_tasks_run_inside_a_business_or_say_why_not() -> None:
    """Tasks in apps/*/tasks.py use @tenant_task; anything else needs a platform-scope marker."""
    offenders = []
    for path in sorted((BACKEND / "apps").glob("*/tasks.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            declares_task = re.search(r"@(shared_task|app\.task|celery_app\.task)\b", line)
            if declares_task and not re.search(r"#\s*platform-scope:\s*\S", line):
                offenders.append(f"{path.relative_to(BACKEND)}:{number}: {line.strip()}")
    assert not offenders, "Use @tenant_task, or mark platform jobs:\n" + "\n".join(offenders)


def test_only_the_notification_handler_talks_to_sms_backends() -> None:
    """SMS leave only through the outbox (CLAUDE.md section 6.4)."""
    allowed = {
        BACKEND / "apps" / "notifications" / "handlers.py",
        BACKEND / "apps" / "notifications" / "backends.py",
    }
    offenders = [
        str(path.relative_to(BACKEND))
        for path in python_files()
        if path not in allowed
        and "tests" not in path.parts
        and "get_sms_backend" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, "Send SMS with send_sms(); found direct backend use in: " + ", ".join(
        offenders
    )


# CLAUDE.md section 6.6: core <- tenancy <- branches <- accounts <- customers / catalog
# <- orders <- payments / riders <- notifications / support / billing.
APP_RANK = {
    "core": 0,
    "tenancy": 1,
    "branches": 2,
    "accounts": 3,
    "customers": 4,
    "catalog": 4,
    "orders": 5,
    "payments": 6,
    "riders": 6,
    "notifications": 7,
    "support": 7,
    "billing": 7,
}


def test_app_dependencies_point_one_way() -> None:
    """An app may import only from apps before it in the order (tests excluded)."""
    import ast

    offenders = []
    for app, rank in APP_RANK.items():
        for path in (BACKEND / "apps" / app).rglob("*.py"):
            if {"tests", "testing", "migrations"} & set(path.parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                for name in names:
                    parts = name.split(".")
                    if len(parts) > 1 and parts[0] == "apps" and parts[1] != app:
                        target = parts[1]
                        if APP_RANK.get(target, 99) >= rank:
                            offenders.append(
                                f"{path.relative_to(BACKEND)}:{getattr(node, 'lineno', 0)}: "
                                f"{app} imports {target}"
                            )
    assert not offenders, "App imports against the dependency order:\n" + "\n".join(offenders)
