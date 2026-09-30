"""Local development on Windows. Business hosts are *.localhost (CLAUDE.md section 7)."""

from config.settings.base import *  # noqa: F403
from config.settings.base import ALLOWED_HOSTS, env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# Chrome and Edge resolve *.localhost to 127.0.0.1, so each business gets its
# own address in development: mamasafi.localhost, cleanpro.localhost.
ALLOWED_HOSTS = [*ALLOWED_HOSTS, ".localhost", "localhost", "127.0.0.1"]
