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
