from django.db import models

from apps.core.models import TenantModel


class Widget(TenantModel):
    name = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="widget_unique_name"),
        ]

    def __str__(self) -> str:
        return self.name
