"""Brand colour checks (10-screens-shared.md, "Design system").

"If the primary colour fails WCAG AA contrast against white text, the console
refuses it." WCAG 2.1 AA for normal text is a contrast ratio of at least 4.5:1.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

WCAG_AA_NORMAL_TEXT = 4.5
WHITE = "#FFFFFF"
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_hex_color(value: str) -> None:
    if not _HEX.fullmatch(value):
        raise ValidationError(_("Enter a colour like #0F6B5C."), code="invalid_color")


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    validate_hex_color(hex_color)
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def validate_primary_color(value: str) -> None:
    """The primary colour carries white text, so it must reach AA against white."""
    validate_hex_color(value)
    if contrast_ratio(value, WHITE) < WCAG_AA_NORMAL_TEXT:
        raise ValidationError(
            _("This colour is too light for white text. Choose a darker shade."),
            code="low_contrast",
        )
