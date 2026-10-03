"""Sections other apps add to GET /business/config (X-01).

The config endpoint lives in tenancy, which may not import the apps above it
(CLAUDE.md section 6.6). So an app that has something the apps need at start-up
registers a section here from its AppConfig.ready(): a name, the serializer for
the schema, and a function that builds the data for the current business. The
catalogue adds its price list this way (M2 T09); delivery areas follow in M9.

Everything in config is public (no sign-in), so a section never holds anything
private.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rest_framework import serializers


@dataclass(frozen=True)
class ConfigSection:
    name: str
    serializer: type[serializers.Serializer[Any]]
    build: Callable[[], Any]  # runs inside the business's context


SECTIONS: dict[str, ConfigSection] = {}


def register_config_section(section: ConfigSection) -> None:
    existing = SECTIONS.get(section.name)
    if existing is not None and existing != section:
        raise ValueError(f"A config section named {section.name!r} is already registered.")
    SECTIONS[section.name] = section
