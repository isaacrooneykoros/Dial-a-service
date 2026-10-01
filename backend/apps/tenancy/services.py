"""Write operations for the tenancy app. Other apps call these, never the models directly."""

from typing import Any

from apps.tenancy.models import BusinessSetting
from apps.tenancy.settings_registry import get_spec


def set_setting(key: str, value: Any) -> None:
    """Store a declared setting for the current business, checking its type."""
    get_spec(key).validate(value)
    BusinessSetting.objects.update_or_create(key=key, defaults={"value": value})
