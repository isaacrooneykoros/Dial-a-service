"""Every error has the same envelope, safe messages, and rolls back (M1 task T03b)."""

import logging
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import transaction
from django.http import Http404
from rest_framework import exceptions, serializers
from rest_framework.authentication import BaseAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from apps.core.api.errors import MESSAGES, ConflictError, GoneError, envelope, error_json
from apps.core.api.exceptions import exception_handler, flatten_errors
from apps.core.api.views import not_found, server_error

factory = APIRequestFactory()


class BearerScheme(BaseAuthentication):
    """Stands in for the real token authentication (T05b): no user, but a scheme,
    so DRF answers authentication errors with 401 rather than 403."""

    def authenticate(self, request: Request) -> None:
        return None

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"


def view_raising(exc: Exception) -> Any:
    @api_view(["GET", "POST"])
    @authentication_classes([BearerScheme])
    @permission_classes([AllowAny])
    def view(request: Request) -> Response:
        raise exc

    return view


def call(exc: Exception, method: str = "get") -> Response:
    request = getattr(factory, method)("/x", HTTP_X_REQUEST_ID="req-1234567890")
    request.request_id = "req-1234567890"
    response: Response = view_raising(exc)(request)
    return response


class PhoneSerializer(serializers.Serializer[Any]):
    phone = serializers.CharField(max_length=5)
    items = serializers.ListField(child=serializers.IntegerField(max_value=3))


class TestEnvelopeShape:
    @pytest.mark.parametrize(
        ("exc", "status", "code"),
        [
            (exceptions.ParseError(), 400, "malformed_request"),
            (exceptions.NotAuthenticated(), 401, "not_authenticated"),
            (exceptions.AuthenticationFailed("Token signature invalid"), 401, "not_authenticated"),
            (exceptions.PermissionDenied(), 403, "permission_denied"),
            (exceptions.NotFound("No Order matches the given query."), 404, "not_found"),
            (exceptions.MethodNotAllowed("PATCH"), 405, "method_not_allowed"),
            (exceptions.NotAcceptable(), 406, "not_acceptable"),
            (exceptions.UnsupportedMediaType("text/xml"), 415, "unsupported_media_type"),
            (Http404("Order DAS-1 not found"), 404, "not_found"),
            (DjangoPermissionDenied(), 403, "permission_denied"),
        ],
    )
    def test_builtin_errors_use_our_safe_messages(
        self, exc: Exception, status: int, code: str
    ) -> None:
        response = call(exc)
        assert response.status_code == status
        assert response.data == {
            "code": code,
            "message": str(MESSAGES[code]),
            "fields": {},
            "request_id": "req-1234567890",
        }

    def test_developer_text_never_leaks(self) -> None:
        response = call(exceptions.AuthenticationFailed("Token signature invalid"))
        assert "signature" not in str(response.data)

    def test_validation_errors_list_fields(self) -> None:
        serializer = PhoneSerializer(data={"phone": "0712345678", "items": [1, 9]})
        assert not serializer.is_valid()
        response = call(exceptions.ValidationError(serializer.errors))
        assert response.status_code == 400
        assert response.data["code"] == "validation_error"
        assert set(response.data["fields"]) == {"phone", "items.1"}

    def test_api_errors_keep_their_own_code_and_message(self) -> None:
        response = call(ConflictError("This code was already used on MSF-4H2K8P", code="code_used"))
        assert response.status_code == 409
        assert response.data["code"] == "code_used"
        assert response.data["message"] == "This code was already used on MSF-4H2K8P"

    def test_api_error_defaults(self) -> None:
        response = call(GoneError())
        assert response.status_code == 410
        assert response.data["code"] == "gone"
        assert response.data["message"] == str(MESSAGES["gone"])

    def test_api_error_with_field_details(self) -> None:
        response = call(ConflictError({"phone": ["Already invited"]}))
        assert response.data["code"] == "conflict"
        assert response.data["fields"] == {"phone": ["Already invited"]}
        assert response.data["message"] == str(MESSAGES["conflict"])


class TestThrottled:
    @pytest.mark.parametrize(
        ("wait", "message", "retry_after"),
        [
            (5, "Too many attempts. Try again in 1 minute.", 5),
            (60, "Too many attempts. Try again in 1 minute.", 60),
            (61, "Too many attempts. Try again in 2 minutes.", 61),
            (899.2, "Too many attempts. Try again in 15 minutes.", 900),
        ],
    )
    def test_message_and_retry_after(self, wait: float, message: str, retry_after: int) -> None:
        response = call(exceptions.Throttled(wait=wait))
        assert response.status_code == 429
        assert response.data["code"] == "throttled"
        assert response.data["message"] == message
        assert response.data["retry_after"] == retry_after

    def test_unknown_wait(self) -> None:
        response = call(exceptions.Throttled(wait=None))
        assert response.data["retry_after"] is None


class TestUnexpectedErrors:
    def test_become_a_500_envelope_and_are_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR):
            response = call(RuntimeError("secret internals: dsn=postgres://x"))
        assert response.status_code == 500
        assert response.data["code"] == "server_error"
        assert "internals" not in str(response.data)
        assert "Unhandled error" in caplog.text


@pytest.mark.django_db
class TestRollback:
    def test_error_marks_the_request_transaction_for_rollback(self) -> None:
        with transaction.atomic():
            exception_handler(exceptions.ValidationError({"x": ["bad"]}), {"request": None})
            assert transaction.get_rollback()
            transaction.set_rollback(False)

    def test_no_transaction_is_fine(self) -> None:
        response = exception_handler(exceptions.NotFound(), {"request": None})
        assert response.status_code == 404


class TestFlattenErrors:
    @pytest.mark.parametrize(
        ("detail", "expected"),
        [
            ({"a": ["x"]}, {"a": ["x"]}),
            ({"a": {"b": ["x", "y"]}}, {"a.b": ["x", "y"]}),
            ({"items": [{}, {"qty": ["too big"]}]}, {"items.1.qty": ["too big"]}),
            (["whole form is wrong"], {"non_field_errors": ["whole form is wrong"]}),
            ("plain", {"non_field_errors": ["plain"]}),
            ({"non_field_errors": ["mismatch"]}, {"non_field_errors": ["mismatch"]}),
        ],
    )
    def test_shapes(self, detail: Any, expected: dict[str, list[str]]) -> None:
        assert flatten_errors(detail) == expected


class TestDjangoHandlers:
    def test_not_found_handler(self) -> None:
        request = factory.get("/nope")
        request.request_id = "rid-12345678"
        response = not_found(request)
        assert response.status_code == 404
        assert response["Content-Type"] == "application/json"
        assert response.content == (
            b'{"code": "not_found", "message": "We couldn\'t find that", '
            b'"fields": {}, "request_id": "rid-12345678"}'
        )

    def test_server_error_handler(self) -> None:
        response = server_error(factory.get("/boom"))
        assert response.status_code == 500

    def test_error_json_without_request(self) -> None:
        assert error_json(None, 404, "not_found").status_code == 404

    def test_envelope_extra_keys(self) -> None:
        assert envelope("x", "y", request_id="r", retry_after=3)["retry_after"] == 3


@pytest.mark.django_db
def test_unknown_api_url_returns_envelope(client: Any) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "not_found"
    assert body["request_id"] == response["X-Request-ID"]
