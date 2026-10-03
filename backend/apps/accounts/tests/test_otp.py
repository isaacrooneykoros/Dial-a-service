"""SMS code rules (M1 T05c; X-11, X-12; ADR-0002 section 4)."""

import re
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
import time_machine
from django.utils import timezone

from apps.accounts.models import PhoneOTP
from apps.accounts.services import otp
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import host_of
from apps.notifications.backends import LocmemSmsBackend
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

PHONE = "+254712345678"
RESET = PhoneOTP.Purpose.PASSWORD_RESET


@pytest.fixture(autouse=True)
def sms() -> Iterator[list[Any]]:
    LocmemSmsBackend.outbox.clear()
    yield LocmemSmsBackend.outbox
    LocmemSmsBackend.outbox.clear()


def send(business: Business, capture: Callable[..., Any], **kwargs: Any) -> otp.SendResult:
    with tenant_context(business.id), capture(execute=True):
        return otp.send_code(PHONE, RESET, **kwargs)


def code_from(sms: list[Any]) -> str:
    match = re.match(r"^(\d{6}) is your ", sms[-1].text)
    assert match, sms[-1].text
    return match[1]


def verify(business: Business, code: str) -> otp.VerifyResult:
    with tenant_context(business.id):
        return otp.verify_code(PHONE, RESET, code)


def test_the_code_arrives_by_sms_through_the_outbox(
    business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    assert send(business_a, django_capture_on_commit_callbacks).ok
    assert sms[-1].to == PHONE
    lines = sms[-1].text.splitlines()
    assert lines[0].endswith(" is your Business-A code. It expires in 10 minutes. Never share it.")
    # D-51: the last line lets Android fill the code in by itself (WebOTP).
    assert lines[-1] == f"@{host_of(business_a)} #{code_from(sms)}"
    with tenant_context(business_a.id):
        stored = PhoneOTP.objects.get()
    assert code_from(sms) not in stored.code_hash  # only a hash is kept


def test_a_correct_code_gives_a_single_use_grant(
    business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    send(business_a, django_capture_on_commit_callbacks)
    result = verify(business_a, code_from(sms))
    assert result.ok
    assert result.grant
    assert not verify(business_a, code_from(sms)).ok  # used
    with tenant_context(business_a.id):
        assert otp.spend_grant(result.grant, RESET) is not None
        assert otp.spend_grant(result.grant, RESET) is None  # single use
        assert otp.spend_grant("", RESET) is None
        assert otp.spend_grant("made-up", RESET) is None


def test_grants_expire_after_10_minutes(
    business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    send(business_a, django_capture_on_commit_callbacks)
    grant = verify(business_a, code_from(sms)).grant
    with time_machine.travel(timezone.now() + timedelta(minutes=11)), tenant_context(business_a.id):
        assert otp.spend_grant(grant, RESET) is None


def test_attempts_left_then_dead_after_five_wrong_tries(
    business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    send(business_a, django_capture_on_commit_callbacks)
    wrong = "000000" if code_from(sms) != "000000" else "111111"
    left = [verify(business_a, wrong).attempts_left for _ in range(5)]
    assert left == [4, 3, 2, 1, 0]
    result = verify(business_a, code_from(sms))
    assert (result.ok, result.reason) == (False, "code_locked")


def test_codes_expire_after_10_minutes(
    business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    send(business_a, django_capture_on_commit_callbacks)
    with time_machine.travel(timezone.now() + timedelta(minutes=10, seconds=1)):
        assert verify(business_a, code_from(sms)).reason == "code_expired"


def test_a_new_code_cancels_the_old_one(
    business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    send(business_a, django_capture_on_commit_callbacks)
    first = code_from(sms)
    with time_machine.travel(timezone.now() + timedelta(seconds=61)):
        send(business_a, django_capture_on_commit_callbacks)
        second = code_from(sms)
        if first != second:
            assert verify(business_a, first).reason == "invalid_code"
        assert verify(business_a, second).ok


def test_sends_are_60_seconds_apart_and_three_an_hour(
    business_a: Business, django_capture_on_commit_callbacks: Any
) -> None:
    start = timezone.now()
    with time_machine.travel(start, tick=False) as clock:
        assert send(business_a, django_capture_on_commit_callbacks).ok
        too_soon = send(business_a, django_capture_on_commit_callbacks)
        assert (too_soon.ok, too_soon.retry_after) == (False, 60)
        clock.shift(61)
        assert send(business_a, django_capture_on_commit_callbacks).ok
        clock.shift(61)
        assert send(business_a, django_capture_on_commit_callbacks).ok
        clock.shift(61)
        fourth = send(business_a, django_capture_on_commit_callbacks)
        assert not fourth.ok
        assert fourth.retry_after == 3600 - 183
        clock.shift(3600 - 183 + 1)
        assert send(business_a, django_capture_on_commit_callbacks).ok


def test_without_an_account_nothing_is_sent_but_limits_count(
    business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    assert send(business_a, django_capture_on_commit_callbacks, deliver=False).ok
    assert sms == []
    assert verify(business_a, "123456").reason == "invalid_code"
    assert not send(business_a, django_capture_on_commit_callbacks).ok  # 60-second rule applies


def test_limits_are_per_business(
    business_a: Business,
    business_b: Business,
    django_capture_on_commit_callbacks: Any,
) -> None:
    assert send(business_a, django_capture_on_commit_callbacks).ok
    assert send(business_b, django_capture_on_commit_callbacks).ok


def test_a_code_from_another_business_is_unknown_here(
    business_a: Business,
    business_b: Business,
    sms: list[Any],
    django_capture_on_commit_callbacks: Any,
) -> None:
    send(business_a, django_capture_on_commit_callbacks)
    assert verify(business_b, code_from(sms)).reason == "invalid_code"
