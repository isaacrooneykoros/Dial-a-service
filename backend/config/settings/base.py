"""Settings shared by every environment.

Every value that differs between environments, and every secret, comes from an
environment variable through django-environ (CLAUDE.md section 6.7). A local
``backend/.env`` file is read if present; real environment variables win.
"""

from datetime import timedelta
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

# Paths that answer on any host, with no business (ADR-0001 section 1). Keep
# this list tiny: tests/test_code_rules.py fails if anything else is added.
TENANCY_EXEMPT_PATHS: tuple[str, ...] = ("/api/v1/health",)

# --- Applications -------------------------------------------------------------

# django.contrib.auth arrived in T05a together with accounts.User, so no
# migration ever depended on Django's default user table. Django admin (and the
# session tables it needs) belongs to the platform-admin service and is added
# in T12.
DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
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
    "apps.core.request_id.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # The business comes from the host; unknown hosts stop here with a 404.
    # Then the rest of the request runs in that business's transaction.
    "apps.tenancy.middleware.TenantResolutionMiddleware",
    "apps.tenancy.middleware.TenantTransactionMiddleware",
    # Accept-Language picks English or Swahili for messages (design doc "API contract").
    "django.middleware.locale.LocaleMiddleware",
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

# scripts/migrate.ps1 and migrate.sh set DJANGO_USE_MIGRATION_DB=1 so that
# migrations (and only migrations) run as the owner role.
USE_MIGRATION_DB: bool = env.bool("DJANGO_USE_MIGRATION_DB", default=False)
DATABASES = {"default": env.db("DATABASE_MIGRATION_URL" if USE_MIGRATION_DB else "DATABASE_URL")}
DATABASES["default"].setdefault("OPTIONS", {})
# Behind a transaction-mode pooler, prepared statements and server-side cursors
# would leak between clients.
DATABASES["default"]["OPTIONS"]["prepare_threshold"] = None
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=0)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
require_postgres(DATABASES["default"]["ENGINE"])

DATABASE_MIGRATION_URL: str = env("DATABASE_MIGRATION_URL", default="")
# The platform role's URL (dial_platform, BYPASSRLS). Only the platform-admin
# service uses it as its DATABASE_URL; the API reads it here only in tests.
PLATFORM_DATABASE_URL: str = env("PLATFORM_DATABASE_URL", default="")
# The dial_app URL, kept as a string so the test harness can switch roles.
DATABASE_APP_URL: str = env("DATABASE_URL")
# The migration connection is direct (not pooled) and may keep server-side state.
if USE_MIGRATION_DB:
    DATABASES["default"]["OPTIONS"].pop("prepare_threshold", None)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Users and passwords (ADR-0002 section 1) ----------------------------------

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.BusinessPhoneBackend"]

# Exactly the X-13 checklist: at least 8 characters, not only numbers, not a
# common password.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

SILENCED_SYSTEM_CHECKS = [
    # auth.W004: USERNAME_FIELD (phone) isn't globally unique. It's unique per
    # business; BusinessPhoneBackend looks users up within the current business.
    "auth.W004",
]

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
CELERY_BEAT_SCHEDULE = {
    "sweep-outbox": {"task": "apps.tenancy.tasks.sweep_outbox", "schedule": 60.0},
}

# --- API ----------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.api.exceptions.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.api.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 20,
    # Signed-in by default; public endpoints opt out explicitly (ADR-0002).
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.SessionTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Keyed by business plus user or IP (ADR-0002 section 9; owner-approved D-48).
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.core.api.throttling.BusinessUserThrottle",
        "apps.core.api.throttling.BusinessAnonThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "300/m",
        "anon": "60/m",
        "login_phone": "10/15m",
        "login_ip": "30/15m",
        "code_ip": "20/h",
        "code_check_ip": "30/15m",
        "pin_ip": "30/15m",
    },
}

# Access tokens (ADR-0002 section 3). Refresh tokens are ours, not simplejwt's.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "SIGNING_KEY": SECRET_KEY,
    "ALGORITHM": "HS256",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Links in messages (invitations) point at the business's own address:
# https://mamasafi.dialaservice.co.ke/invite/... Local development adds the
# Vite port: http://mamasafi.localhost:5173/invite/...
APP_LINK_SCHEME: str = env("APP_LINK_SCHEME", default="https")
APP_LINK_PORT: str = env("APP_LINK_PORT", default="")

# Key for hashing SMS codes and the grants they unlock (ADR-0002 section 4).
OTP_HASH_KEY: str = env("OTP_HASH_KEY", default=SECRET_KEY)

# The refresh cookie is Secure everywhere except plain-http local development.
REFRESH_COOKIE_SECURE: bool = env.bool("REFRESH_COOKIE_SECURE", default=True)

SPECTACULAR_SETTINGS = {
    "TITLE": "Dial A Service API",
    "DESCRIPTION": "One API for every business; the business comes from the host.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Logging ------------------------------------------------------------------
# JSON lines with request IDs; phone numbers masked and secrets redacted
# (apps/core/logging.py, CLAUDE.md section 6.7).

LOG_LEVEL: str = env("DJANGO_LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "apps.core.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # SQL is never logged: it can carry phone numbers in parameters.
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# --- Notifications ------------------------------------------------------------
# Development prints SMS to the terminal. The real gateway backend arrives with
# the gateway decision (OPEN.md D-08). TODO(decision): sms-gateway
SMS_BACKEND: str = env("SMS_BACKEND", default="apps.notifications.backends.ConsoleSmsBackend")

# --- Error tracking -----------------------------------------------------------

SENTRY_DSN: str = env("SENTRY_DSN", default="")
