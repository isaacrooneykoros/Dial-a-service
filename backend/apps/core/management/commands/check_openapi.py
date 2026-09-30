"""Compare the generated OpenAPI schema with the committed backend/openapi.yaml.

    python manage.py check_openapi           # exit 1 if the committed file is stale
    python manage.py check_openapi --write   # regenerate the committed file

CI runs the first form, so every API change is reviewed with its schema diff
(CLAUDE.md section 6.5). The frontend client is generated from this file.
"""

import difflib
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.renderers import OpenApiYamlRenderer
from drf_spectacular.validation import validate_schema

SCHEMA_FILE = Path(settings.BASE_DIR) / "openapi.yaml"


def generate_schema() -> str:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    validate_schema(schema)
    rendered: bytes = OpenApiYamlRenderer().render(schema, renderer_context={})
    return rendered.decode("utf-8")


class Command(BaseCommand):
    help = "Fail if backend/openapi.yaml differs from the generated schema (--write updates it)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--write", action="store_true", help="Rewrite openapi.yaml")

    def handle(self, *args: Any, **options: Any) -> None:
        generated = generate_schema()
        if options["write"]:
            SCHEMA_FILE.write_text(generated, encoding="utf-8", newline="\n")
            self.stdout.write(f"Wrote {SCHEMA_FILE.name}")
            return

        committed = SCHEMA_FILE.read_text(encoding="utf-8") if SCHEMA_FILE.exists() else ""
        if committed == generated:
            self.stdout.write("openapi.yaml is up to date")
            return

        diff = difflib.unified_diff(
            committed.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile="openapi.yaml (committed)",
            tofile="openapi.yaml (generated)",
        )
        self.stderr.write("".join(diff))
        raise CommandError(
            "openapi.yaml is out of date. Run: python manage.py check_openapi --write"
        )
