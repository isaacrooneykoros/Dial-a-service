"""Every request gets an ID, echoed in the response and available to logs (M1 task T03a)."""

import re

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from apps.core.request_id import HEADER, RequestIDMiddleware, get_request_id

factory = RequestFactory()


def run(**headers: str) -> tuple[HttpResponse, list[str | None]]:
    seen: list[str | None] = []

    def view(request: HttpRequest) -> HttpResponse:
        seen.append(get_request_id())
        seen.append(getattr(request, "request_id", None))
        return HttpResponse("ok")

    response = RequestIDMiddleware(view)(factory.get("/", headers=headers))
    return response, seen


def test_generates_an_id_when_none_is_sent() -> None:
    response, seen = run()
    request_id = response[HEADER]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)
    assert seen == [request_id, request_id]


def test_echoes_a_valid_incoming_id() -> None:
    response, seen = run(**{HEADER: "cf-ray-8a1b2c3d4e"})
    assert response[HEADER] == "cf-ray-8a1b2c3d4e"
    assert seen[0] == "cf-ray-8a1b2c3d4e"


@pytest.mark.parametrize(
    "bad",
    ["short", "x" * 65, "has spaces in it", "bad<script>id", "line\nbreak-123456"],
)
def test_replaces_an_unsafe_incoming_id(bad: str) -> None:
    response, _ = run(**{HEADER: bad})
    assert response[HEADER] != bad
    assert re.fullmatch(r"[0-9a-f]{32}", response[HEADER])


def test_each_request_gets_a_new_id() -> None:
    first, _ = run()
    second, _ = run()
    assert first[HEADER] != second[HEADER]


def test_context_is_cleared_after_the_request() -> None:
    run()
    assert get_request_id() is None


def test_context_is_cleared_when_the_view_raises() -> None:
    def broken(request: HttpRequest) -> HttpResponse:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        RequestIDMiddleware(broken)(factory.get("/"))
    assert get_request_id() is None
