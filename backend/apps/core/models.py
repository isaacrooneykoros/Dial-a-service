"""Base models shared by every app."""

import uuid

from django.db import models


class BaseModel(models.Model):
    """UUID primary key and UTC timestamps (design doc "Data model").

    IDs are random UUIDs so they can be exposed through the API without
    revealing counts or ordering.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
