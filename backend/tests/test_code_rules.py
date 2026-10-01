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
