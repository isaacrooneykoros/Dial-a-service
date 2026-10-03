"""Notification templates and the messages sent (design doc, notifications app)."""

import string

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.notifications.catalogue import EVENTS, SMS, max_template_length


def template_placeholders(body: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(body) if name}


class NotificationTemplate(TenantModel):
    """A business's own wording for one event, channel and language.

    Without one, the catalogue default is used (apps/notifications/catalogue.py).
    """

    class Channel(models.TextChoices):
        SMS = SMS, _("SMS")

    event = models.CharField(max_length=64)
    channel = models.CharField(max_length=8, choices=Channel.choices, default=Channel.SMS)
    language = models.CharField(max_length=2)
    body = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "event", "channel", "language"], name="one_template_per_event"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event}/{self.channel}/{self.language}"

    def clean(self) -> None:
        event = EVENTS.get(self.event)
        if event is None:
            raise ValidationError({"event": _("Unknown message type.")})
        unknown = template_placeholders(self.body) - event.placeholders
        if unknown:
            raise ValidationError(
                {
                    "body": _("Unknown placeholder: %(names)s")
                    % {"names": ", ".join(sorted(unknown))}
                }
            )
        limit = max_template_length(event)
        if self.channel == SMS and len(self.body) > limit:
            raise ValidationError(
                {"body": _("Keep it within %(n)d characters so it costs one SMS.") % {"n": limit}}
            )


class Notification(TenantModel):
    """One message to one person, sent through the outbox (CLAUDE.md section 6.4).

    ``context`` holds the placeholder values until the message is sent or given
    up; then sensitive values (codes, links) are removed and ``body`` keeps a
    copy with them masked.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        SENT = "sent", _("Sent")
        FAILED = "failed", _("Failed")

    recipient_phone = models.CharField(max_length=16)
    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    event = models.CharField(max_length=64)
    channel = models.CharField(max_length=8, default=SMS)
    language = models.CharField(max_length=2, default="en")
    context = models.JSONField(default=dict)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    provider_message_id = models.CharField(max_length=100, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    # SMS cost and the business's SMS balance arrive with billing (M4/M6, OPEN.md D-33).

    class Meta:
        indexes = [
            models.Index(fields=["business", "created_at"], name="notification_business_time"),
        ]

    def __str__(self) -> str:
        return f"{self.event} to {self.recipient_phone} ({self.status})"
