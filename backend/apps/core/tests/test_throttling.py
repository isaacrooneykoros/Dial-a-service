"""Business-scoped throttle rates accept periods like 15 minutes (M1 T05b)."""

import pytest

from apps.core.api.throttling import BusinessThrottle


class Probe(BusinessThrottle):
    scope = "anon"


@pytest.mark.parametrize(
    ("rate", "parsed"),
    [("10/15m", (10, 900)), ("60/m", (60, 60)), ("3/h", (3, 3600)), ("5/2d", (5, 172800))],
)
def test_parse_rate(rate: str, parsed: tuple[int, int]) -> None:
    assert Probe().parse_rate(rate) == parsed


def test_no_rate_means_no_limit() -> None:
    assert Probe().parse_rate(None) == (None, None)


@pytest.mark.parametrize("rate", ["10", "10/15", "ten/m", "10/15w"])
def test_bad_rates_are_refused(rate: str) -> None:
    with pytest.raises(ValueError, match="Bad throttle rate"):
        Probe().parse_rate(rate)


def test_subclasses_must_say_what_they_limit() -> None:
    with pytest.raises(NotImplementedError):
        Probe().subject(None)
