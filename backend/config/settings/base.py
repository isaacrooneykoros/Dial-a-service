"""Settings shared by every environment.

Every value that differs between environments, and every secret, comes from an
environment variable through django-environ (CLAUDE.md section 6.7). A local
``backend/.env`` file is read if present; real environment variables win.
"""

from pathlib import Path

import environ

from config.settings.checks import require_postgres

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env()
# DJANGO_READ_DOT_ENV=0 skips the file (used by tests that need a clean environment).
if env.bool("DJANGO_READ_DOT_ENV", default=True):
    environ.Env.read_env(BASE_DIR / ".env")

# --- Core -------------------------------------------------------------------

SECRET_KEY: str = env("DJANGO_SECRET_KEY")
DEBUG: bool = env.bool("DJANGO_DEBUG", default=False)

# Which process this is: "api" (business hosts) or "platform_admin" (Django admin
# on PLATFORM_ADMIN_HOST, connecting as dial_platform). See ADR-0001 section 6.
DJANGO_SERVICE: str = env("DJANGO_SERVICE", default="api")

PLATFORM_ROOT_DOMAIN: str = env("PLATFORM_ROOT_DOMAIN", default="dialaservice.co.ke")
PLATFORM_ADMIN_HOST: str = env("PLATFORM_ADMIN_HOST", default=f"admin.{PLATFORM_ROOT_DOMAIN}")
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# --- Applications -------------------------------------------------------------

# django.contrib.auth is added in M1 task T05a together with the custom
# accounts.User and AUTH_USER_MODEL, so no migration ever depends on Django's
# default user table (kickoff T05; docs/plans/M1.md T01b).
DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
]

# Listed in dependency order (CLAUDE.md section 6.6, ADR-0001 section 8).
LOCAL_APPS = [
    "apps.core",
    "apps.tenancy",
    "apps.branches",
    "apps.accounts",
    "apps.customers",
    "apps.catalog",
    "apps.orders",
    "apps.payments",
    "apps.riders",
    "apps.notifications",
    "apps.support",
    "apps.billing",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # DRF views are CSRF-exempt (bearer tokens); this protects Django admin.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

# --- Database -----------------------------------------------------------------
# DATABASE_URL is the dial_app role (subject to row-level security), through
# Neon's pooled host. Migrations use DATABASE_MIGRATION_URL (dial_owner) via
# scripts/migrate.ps1 only. See ADR-0001 section 5.

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"].setdefault("OPTIONS", {})
# Behind a transaction-mode pooler, prepared statements and server-side cursors
# would leak between clients.
DATABASES["default"]["OPTIONS"]["prepare_threshold"] = None
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=0)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
require_postgres(DATABASES["default"]["ENGINE"])

DATABASE_MIGRATION_URL: str = env("DATABASE_MIGRATION_URL", default="")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Internationalisation -----------------------------------------------------

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("sw", "Kiswahili")]
USE_I18N = True
TIME_ZONE = "UTC"
USE_TZ = True

# --- Static files (Django admin only; the apps are served by Cloudflare Pages) --

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Cache and background work ------------------------------------------------
# With no REDIS_URL (local development only; production refuses it), the cache
# is in memory and Celery runs tasks eagerly. See ADR-0001 section 6.

REDIS_URL: str = env("REDIS_URL", default="")

if REDIS_URL:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = "UTC"

# --- API ----------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Authentication arrives in T05b; until then nothing is authenticated and
    # DRF must not touch django.contrib.auth.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Dial A Service API",
    "DESCRIPTION": "One API for every business; the business comes from the host.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Error tracking -----------------------------------------------------------

SENTRY_DSN: str = env("SENTRY_DSN", default="")
