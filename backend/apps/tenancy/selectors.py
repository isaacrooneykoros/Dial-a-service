"""Read queries for the tenancy app. Other apps call these, never the models directly."""

from typing import Any

from apps.tenancy.models import BusinessSetting
from apps.tenancy.settings_registry import get_spec


def get_setting(key: str) -> Any:
    """The current business's value for a declared setting, or its default."""
    spec = get_spec(key)
    row = BusinessSetting.objects.filter(key=key).values_list("value", flat=True).first()
    return spec.default if row is None else row
