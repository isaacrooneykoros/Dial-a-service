# Run Django migrations as the owner role (dial_owner), never as dial_app.
# Usage, from backend\ with the virtualenv active:
#   .\scripts\migrate.ps1                  # all migrations
#   .\scripts\migrate.ps1 tenancy 0002     # any arguments are passed to "migrate"
# Reads DATABASE_MIGRATION_URL from backend\.env (ADR-0001 section 5).

$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $PSScriptRoot
# Use the project's virtualenv even if it isn't activated.
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
Push-Location $backend
try {
    $env:DJANGO_USE_MIGRATION_DB = "1"
    & $python manage.py migrate @args
    if ($LASTEXITCODE -ne 0) { throw "migrate failed with exit code $LASTEXITCODE" }
    # New tables need the app grants (default privileges cover most; this is the safety net).
    & $python -m scripts.db.setup_roles --grants-only
    if ($LASTEXITCODE -ne 0) { throw "granting privileges failed with exit code $LASTEXITCODE" }
}
finally {
    Remove-Item Env:DJANGO_USE_MIGRATION_DB -ErrorAction SilentlyContinue
    Pop-Location
}
