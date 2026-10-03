"""SMS through the outbox, with the catalogue wording (M1 T07b, CLAUDE.md section 6.4)."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import OutboxEvent
from apps.core.tasks import handle
from apps.core.tenant_context import tenant_context
from apps.notifications import handlers
from apps.notifications.backends import ConsoleSmsBackend, LocmemSmsBackend
from apps.notifications.models import Notification, NotificationTemplate
from apps.notifications.services import render, send_sms, template_text
from apps.tenancy.models import Business
from apps.tenancy.tests.factories import BusinessDomainFactory, BusinessFactory

pytestmark = pytest.mark.django_db

PHONE = "+254712345678"
CODE_CONTEXT = {"code": "482913", "business": "Mama Safi"}
CODE_TEXT = "482913 is your Mama Safi code. It expires in 10 minutes. Never share it."


@pytest.fixture(autouse=True)
def sms_outbox() -> Iterator[list[Any]]:
    LocmemSmsBackend.outbox.clear()
    yield LocmemSmsBackend.outbox
    LocmemSmsBackend.outbox.clear()


@pytest.fixture
def business() -> Business:
    return BusinessFactory()


class TestCatalogueWording:
    def test_phone_code_text_is_the_catalogue_text(self, business: Business) -> None:
        with tenant_context(business.id):
            assert render("phone_code", "en", CODE_CONTEXT) == CODE_TEXT

    def test_invitation_text_is_the_catalogue_text(self, business: Business) -> None:
        context = {"business": "Mama Safi", "role": "Shop staff", "link": "https://x/i/abc"}
        with tenant_context(business.id):
            assert render("invitation", "en", context) == (
                "Mama Safi invited you to join as Shop staff. Set up your account: https://x/i/abc"
            )

    def test_swahili_falls_back_to_english_until_translated(self, business: Business) -> None:
        with tenant_context(business.id):
            assert render("phone_code", "sw", CODE_CONTEXT) == CODE_TEXT

    def test_a_business_template_wins(self, business: Business) -> None:
        with tenant_context(business.id):
            NotificationTemplate.objects.create(
                event="phone_code", language="sw", body="{code} ni nambari yako ya {business}."
            )
            assert render("phone_code", "sw", CODE_CONTEXT) == (
                "482913 ni nambari yako ya Mama Safi."
            )
            assert render("phone_code", "en", CODE_CONTEXT) == CODE_TEXT

    def test_missing_values_are_an_error_for_the_caller(self, business: Business) -> None:
        with tenant_context(business.id), pytest.raises(KeyError, match="code"):
            send_sms("phone_code", to=PHONE, context={"business": "Mama Safi"})

    def test_unknown_event(self, business: Business) -> None:
        with tenant_context(business.id), pytest.raises(KeyError, match="Unknown"):
            template_text("nope", "en")


class TestAutomaticCodeFill:
    """D-51: code messages end with the WebOTP line Android Chrome reads."""

    def test_code_messages_end_with_the_web_address_and_code(self) -> None:
        domain = BusinessDomainFactory(host="mamasafi.dialaservice.co.ke")
        with tenant_context(domain.business_id):
            text = render("phone_code", "en", CODE_CONTEXT)
        assert text == f"{CODE_TEXT}\n\n@mamasafi.dialaservice.co.ke #482913"
        assert text.splitlines()[-1] == "@mamasafi.dialaservice.co.ke #482913"
        assert len(text) <= 160

    def test_a_business_template_still_gets_the_line(self) -> None:
        domain = BusinessDomainFactory(host="mamasafi.localhost")
        with tenant_context(domain.business_id):
            NotificationTemplate.objects.create(
                event="phone_code", language="en", body="{code} ni nambari yako ya {business}."
            )
            assert render("phone_code", "en", CODE_CONTEXT) == (
                "482913 ni nambari yako ya Mama Safi.\n\n@mamasafi.localhost #482913"
            )

    def test_the_stored_copy_masks_the_code_in_the_line_too(self) -> None:
        domain = BusinessDomainFactory(host="mamasafi.localhost")
        with tenant_context(domain.business_id):
            text = render("phone_code", "en", CODE_CONTEXT, masked=True)
        assert "482913" not in text
        assert text.endswith("@mamasafi.localhost #••••")

    def test_other_messages_have_no_line(self) -> None:
        domain = BusinessDomainFactory(host="mamasafi.localhost")
        context = {"business": "Mama Safi", "role": "Shop staff", "link": "https://x/i/abc"}
        with tenant_context(domain.business_id):
            assert "@mamasafi.localhost" not in render("invitation", "en", context)

    def test_templates_leave_room_for_the_line(self) -> None:
        with pytest.raises(ValidationError):
            NotificationTemplate(
                event="phone_code", language="en", body="{code} " + "x" * 104
            ).clean()
        NotificationTemplate(event="phone_code", language="en", body="{code} " + "x" * 100).clean()


class TestTemplateValidation:
    def test_valid(self) -> None:
        NotificationTemplate(event="phone_code", language="en", body="{code} {business}").clean()

    @pytest.mark.parametrize(
        ("event", "body", "field"),
        [
            ("nope", "x", "event"),
            ("phone_code", "{code} {secret}", "body"),
            ("phone_code", "{code} " + "x" * 160, "body"),
        ],
    )
    def test_invalid(self, event: str, body: str, field: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            NotificationTemplate(event=event, language="en", body=body).clean()
        assert field in excinfo.value.message_dict


class TestSending:
    def test_nothing_is_sent_before_commit_then_it_is(
        self,
        business: Business,
        sms_outbox: list[Any],
        django_capture_on_commit_callbacks: Callable[..., Any],
    ) -> None:
        with tenant_context(business.id):
            with django_capture_on_commit_callbacks(execute=True):
                notification = send_sms("phone_code", to=PHONE, context=CODE_CONTEXT)
                assert sms_outbox == []
            notification.refresh_from_db()
        assert [(m.to, m.text) for m in sms_outbox] == [(PHONE, CODE_TEXT)]
        assert notification.status == Notification.Status.SENT
        assert notification.sent_at is not None
        assert notification.provider_message_id.startswith("locmem-")

    def test_codes_are_removed_from_what_is_stored(
        self, business: Business, django_capture_on_commit_callbacks: Callable[..., Any]
    ) -> None:
        with tenant_context(business.id):
            with django_capture_on_commit_callbacks(execute=True):
                notification = send_sms("phone_code", to=PHONE, context=CODE_CONTEXT)
            notification.refresh_from_db()
        assert "482913" not in str(notification.context)
        assert "482913" not in notification.body
        assert notification.body.startswith("•••• is your Mama Safi code")

    def test_sending_twice_sends_once(self, business: Business, sms_outbox: list[Any]) -> None:
        with tenant_context(business.id):
            notification = send_sms("phone_code", to=PHONE, context=CODE_CONTEXT)
            event = OutboxEvent.objects.get(type="notification.send")
            handlers.send_notification(event)
            handlers.send_notification(event)
            notification.refresh_from_db()
        assert len(sms_outbox) == 1
        assert notification.attempts == 1


class FlakyBackend:
    def send(self, to: str, text: str) -> Any:
        raise ConnectionError("gateway timeout")


class TestFailures:
    @pytest.fixture(autouse=True)
    def flaky_gateway(self, settings: Any) -> None:
        settings.SMS_BACKEND = "apps.notifications.tests.test_notifications.FlakyBackend"

    def test_retried_three_times_over_15_minutes_then_failed(self, business: Business) -> None:
        with tenant_context(business.id):
            notification = send_sms("phone_code", to=PHONE, context=CODE_CONTEXT)
            for attempt in range(1, 5):
                event = (
                    OutboxEvent.objects.filter(type="notification.send", processed_at__isnull=True)
                    .order_by("created_at")
                    .first()
                )
                assert event is not None
                before = timezone.now()
                handle(event)  # never raises into the caller
                notification.refresh_from_db()
                assert notification.attempts == attempt
                if attempt <= 3:
                    assert notification.status == Notification.Status.PENDING
                    retry = OutboxEvent.objects.filter(
                        type="notification.send", processed_at__isnull=True
                    ).get()
                    assert retry.available_at >= before + timedelta(minutes=5)
            assert notification.status == Notification.Status.FAILED
            assert "gateway timeout" in notification.error
            assert "482913" not in str(notification.context)
            assert not OutboxEvent.objects.filter(processed_at__isnull=True).exists()


def test_console_backend_prints_the_message(capsys: pytest.CaptureFixture[str]) -> None:
    sent = ConsoleSmsBackend().send(PHONE, CODE_TEXT)
    out = capsys.readouterr().out
    assert PHONE in out
    assert CODE_TEXT in out
    assert sent.message_id.startswith("console-")


def test_an_event_with_no_text_in_any_language(
    business: Business, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.notifications import catalogue

    event = catalogue.Event("silent", frozenset(), frozenset(), defaults={})
    monkeypatch.setitem(catalogue.EVENTS, "silent", event)
    with tenant_context(business.id), pytest.raises(LookupError, match="No sms text"):
        template_text("silent", "sw")


class TestRequestsFromOtherApps:
    """apps.core.messaging.request_sms: how earlier apps (accounts) send SMS."""

    def test_request_becomes_a_sent_notification_and_the_code_leaves_the_event(
        self,
        business: Business,
        sms_outbox: list[Any],
        django_capture_on_commit_callbacks: Callable[..., Any],
    ) -> None:
        from apps.core.messaging import request_sms

        with tenant_context(business.id):
            with django_capture_on_commit_callbacks(execute=True):
                request_sms("phone_code", to=PHONE, context=CODE_CONTEXT)
            event = OutboxEvent.objects.get(type="notification.request")
            notification = Notification.objects.get()
        assert [m.text for m in sms_outbox] == [CODE_TEXT]
        assert notification.status == Notification.Status.SENT
        assert "482913" not in str(event.payload)
        assert event.payload["notification_id"] == str(notification.pk)

    def test_running_the_request_twice_sends_once(
        self, business: Business, sms_outbox: list[Any]
    ) -> None:
        from apps.core.messaging import request_sms

        with tenant_context(business.id):
            request_sms("phone_code", to=PHONE, context=CODE_CONTEXT)
            event = OutboxEvent.objects.get(type="notification.request")
            handlers.create_requested_notification(event)
            handlers.create_requested_notification(event)
            assert Notification.objects.count() == 1
        assert len(sms_outbox) == 1
