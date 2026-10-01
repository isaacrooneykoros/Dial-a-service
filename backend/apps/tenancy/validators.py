"""Validation for business web addresses (15-platform-and-website.md, W-03)."""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# W-03: "web addresses use a-z, 0-9 and hyphens; reserved words (www, admin,
# api, app, console, staff, rider) are refused." A DNS label also can't start or
# end with a hyphen or be longer than 63 characters.
RESERVED_SLUGS = frozenset({"www", "admin", "api", "app", "console", "staff", "rider"})
SLUG_MAX_LENGTH = 63
_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

# A host as stored in BusinessDomain: lowercase DNS labels, no port.
_HOST = re.compile(
    r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$"
)


def validate_business_slug(value: str) -> None:
    if not _SLUG.fullmatch(value):
        raise ValidationError(
            _(
                "Use only lowercase letters, numbers and hyphens. "
                "It can't start or end with a hyphen."
            ),
            code="invalid_slug",
        )
    if value in RESERVED_SLUGS:
        raise ValidationError(
            _("That web address isn't available. Try another."), code="reserved_slug"
        )


def normalize_host(raw: str) -> str:
    """Lowercase, drop a trailing dot and any port.

    'MamaSafi.Localhost:5173' becomes 'mamasafi.localhost'.
    """
    host = raw.strip().lower()
    if host.startswith("["):  # IPv6 literal; never a business host
        return host
    host = host.rsplit(":", 1)[0] if ":" in host else host
    return host.rstrip(".")


def validate_host(value: str) -> None:
    if not _HOST.fullmatch(value):
        raise ValidationError(_("Enter a valid host name."), code="invalid_host")
