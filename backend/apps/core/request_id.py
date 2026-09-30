"""A request ID on every request, response and log line.

The ID is shown to users as the "support reference" on server errors
(10-screens-shared.md, "Server error"), so support can find the log lines.
"""

import re
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

HEADER = "X-Request-ID"
_META_KEY = "HTTP_X_REQUEST_ID"
# Accept a caller's ID (for example from Cloudflare or the apps) only if it is
# short and harmless to echo and log.
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def new_request_id() -> str:
    return uuid.uuid4().hex


class RequestIDMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.META.get(_META_KEY, "")
        request_id = incoming if _VALID.fullmatch(incoming) else new_request_id()
        request.request_id = request_id  # type: ignore[attr-defined]
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[HEADER] = request_id
        return response
