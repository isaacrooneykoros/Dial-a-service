"""BaseModel gives every table a random UUID key and UTC timestamps (M1 task T03a).

Behaviour on a real table is covered by the first concrete models (T04a).
"""

import uuid

from django.db import models

from apps.core.models import BaseModel


def test_base_model_is_abstract() -> None:
    assert BaseModel._meta.abstract


def test_primary_key_is_a_random_uuid() -> None:
    field = BaseModel._meta.get_field("id")
    assert isinstance(field, models.UUIDField)
    assert field.primary_key
    assert field.default is uuid.uuid4
    assert not field.editable


def test_timestamps() -> None:
    created = BaseModel._meta.get_field("created_at")
    updated = BaseModel._meta.get_field("updated_at")
    assert isinstance(created, models.DateTimeField)
    assert isinstance(updated, models.DateTimeField)
    assert created.auto_now_add
    assert updated.auto_now
