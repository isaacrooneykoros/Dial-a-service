#!/usr/bin/env sh
# Run Django migrations as the owner role (dial_owner), never as dial_app.
# Usage, from backend/: ./scripts/migrate.sh [migrate arguments]
# Reads DATABASE_MIGRATION_URL from the environment or backend/.env (ADR-0001 section 5).
set -eu

cd "$(dirname "$0")/.."
DJANGO_USE_MIGRATION_DB=1 python manage.py migrate "$@"
# New tables need the app grants (default privileges cover most; this is the safety net).
python -m scripts.db.setup_roles --grants-only
