"""Settings for pytest. Tests run against real Postgres as dial_app (ADR-0001 section 7)."""

from config.settings.base import *  # noqa: F403

DEBUG = False

ALLOWED_HOSTS = [".localhost", "testserver"]

# Password hashing is deliberately slow; tests don't need that.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True

# A test-only app with a tenant model (tests/testapp).
INSTALLED_APPS = [*INSTALLED_APPS, "tests.testapp"]  # noqa: F405
