"""The notification catalogue (10-screens-shared.md, "Notification catalogue").

Default texts are the catalogue's English wording, word for word. A business
can have its own version of a template (NotificationTemplate, per language);
otherwise these defaults are used. Swahili defaults are added when the
translations exist (owner decision D-23); until then Swahili falls back to
English.

M1 declares only the messages M1 sends: the phone code and the invitation.
"""

from dataclasses import dataclass

SMS = "sms"


@dataclass(frozen=True)
class Event:
    key: str
    placeholders: frozenset[str]
    # Values removed from the stored message once it has been sent: anything
    # that would let someone sign in or accept an invitation.
    sensitive: frozenset[str]
    defaults: dict[str, str]  # language -> default text
    # The placeholder holding a one-time code. Its message gets a last line for
    # automatic code fill on Android (WebOTP, owner decision D-51).
    webotp_code: str = ""


EVENTS: dict[str, Event] = {
    event.key: event
    for event in (
        Event(
            key="phone_code",
            placeholders=frozenset({"code", "business"}),
            sensitive=frozenset({"code"}),
            defaults={
                "en": "{code} is your {business} code. It expires in 10 minutes. Never share it."
            },
            webotp_code="code",
        ),
        Event(
            key="invitation",
            placeholders=frozenset({"business", "role", "link"}),
            sensitive=frozenset({"link"}),
            defaults={
                "en": "{business} invited you to join as {role}. Set up your account: {link}"
            },
        ),
    )
}

FALLBACK_LANGUAGE = "en"
SMS_MAX_LENGTH = 160  # one SMS
# Room kept for the WebOTP last line (a blank line, then "@{host} #{code}") in code
# messages, so a business's own template plus that line still fits in one SMS.
# 50 covers web addresses up to about 20 characters before ".dialaservice.co.ke".
WEBOTP_LINE_RESERVE = 50


def max_template_length(event: "Event") -> int:
    return SMS_MAX_LENGTH - (WEBOTP_LINE_RESERVE if event.webotp_code else 0)


def get_event(key: str) -> Event:
    try:
        return EVENTS[key]
    except KeyError:
        raise KeyError(f"Unknown notification event {key!r}.") from None
