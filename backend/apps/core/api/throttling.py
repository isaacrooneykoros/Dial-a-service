"""Throttles keyed by business plus IP, user or phone (CLAUDE.md section 6.7; ADR-0002 section 9).

One busy business can never use up another's allowance, and a phone number can
be protected across IP addresses. Rates are in settings (REST_FRAMEWORK
DEFAULT_THROTTLE_RATES) and accept periods such as "10/15m".
"""

import re
from typing import Any

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

_RATE = re.compile(r"^(?P<num>\d+)/(?P<count>\d*)(?P<unit>[smhd])$")
_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class BusinessThrottle(SimpleRateThrottle):
    """Base class: the cache key always starts with the business."""

    def parse_rate(self, rate: str | None) -> tuple[int | None, int | None]:
        if rate is None:
            return (None, None)
        match = _RATE.fullmatch(rate.replace(" ", ""))
        if match is None:
            raise ValueError(f"Bad throttle rate {rate!r}; use forms like '10/15m' or '60/m'.")
        count = int(match["count"] or 1)
        return int(match["num"]), count * _SECONDS[match["unit"]]

    def business_key(self, request: Request) -> str:
        business = getattr(request._request, "business", None)
        return str(business.id) if business is not None else "platform"

    def subject(self, request: Request) -> str | None:
        """What is being limited within the business; None means don't throttle."""
        raise NotImplementedError

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        subject = self.subject(request)
        if subject is None:
            return None
        return f"throttle:{self.scope}:{self.business_key(request)}:{subject}"


class BusinessIPThrottle(BusinessThrottle):
    def subject(self, request: Request) -> str | None:
        ident: str = self.get_ident(request)
        return ident


class BusinessUserThrottle(BusinessThrottle):
    """Signed-in requests: per user. Anonymous ones are left to BusinessAnonThrottle."""

    scope = "user"

    def subject(self, request: Request) -> str | None:
        if request.user and request.user.is_authenticated:
            return str(request.user.pk)
        return None


class BusinessAnonThrottle(BusinessIPThrottle):
    scope = "anon"

    def subject(self, request: Request) -> str | None:
        if request.user and request.user.is_authenticated:
            return None
        return super().subject(request)
