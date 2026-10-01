"""Sign-in endpoints: X-10 log in, silent refresh, log out, and who am I.

Views are thin: shape checks here, rules in apps.accounts.services.auth.
Failures that must leave something behind (a revoked session) are *returned*,
not raised, so the request transaction commits (apps/core/api/exceptions.py).
"""

from typing import Any

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.cookies import (
    clear_refresh_cookie,
    read_refresh_cookie,
    set_refresh_cookie,
)
from apps.accounts.api.serializers import (
    AccessSerializer,
    BranchSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    MeSerializer,
)
from apps.accounts.api.throttling import LoginIPThrottle, LoginPhoneThrottle
from apps.accounts.models import UserSession
from apps.accounts.phones import format_local
from apps.accounts.services import auth
from apps.accounts.tokens import hash_refresh_token
from apps.branches.selectors import branches_for_user
from apps.core.api.errors import envelope
from apps.tenancy.selectors import support_contact

ERROR = {
    400: OpenApiResponse(description="Error envelope"),
    401: OpenApiResponse(description="Error envelope"),
    403: OpenApiResponse(description="Error envelope"),
    429: OpenApiResponse(description="Error envelope with retry_after"),
}


def suspended_message(business_id: Any) -> str:
    name, phone = support_contact(business_id)
    contact = f"{name} on {format_local(phone)}" if phone else name
    # X-10: "Your account is suspended. Contact {business support}"
    return _("Your account is suspended. Contact %(contact)s") % {"contact": contact}


class LoginView(APIView):
    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginPhoneThrottle, LoginIPThrottle]

    @extend_schema(
        operation_id="auth_login",
        summary="X-10 Log in",
        request=LoginSerializer,
        responses={200: LoginResponseSerializer, **ERROR},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            signed_in = auth.login(request, **serializer.validated_data)
        except auth.InvalidCredentialsError:
            # X-10: always this message, never saying which part was wrong.
            message = _("Phone number or password is incorrect")
            return Response(envelope("invalid_credentials", message), status=400)
        except auth.AccountSuspendedError as exc:
            message = suspended_message(exc.user.business_id)
            return Response(envelope("account_suspended", message), status=403)

        body = {"access": signed_in.access, "user": MeSerializer(signed_in.user).data}
        response = Response(body)
        set_refresh_cookie(response, signed_in.refresh)
        return response


class RefreshView(APIView):
    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_refresh",
        summary="Rotate the refresh cookie and get a new access token",
        request=None,
        responses={200: AccessSerializer, **ERROR},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        outcome = auth.refresh(read_refresh_cookie(request._request))
        if not outcome.ok:
            message = _("Your session has ended. Please log in again.")
            response = Response(envelope("session_expired", message), status=401)
            clear_refresh_cookie(response)
            return response
        response = Response({"access": outcome.access})
        set_refresh_cookie(response, outcome.refresh)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_logout",
        summary="Sign out this device",
        request=None,
        responses={204: None},
    )
    def post(self, request: Request) -> Response:
        session = request.auth if isinstance(request.auth, UserSession) else None
        if session is None:
            raw = read_refresh_cookie(request._request)
            if raw:
                session = UserSession.objects.filter(refresh_hash=hash_refresh_token(raw)).first()
        if session is not None:
            auth.logout(session, request=request)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="me", summary="The signed-in person", responses={200: MeSerializer})
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)


class MyBranchesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="me_branches",
        summary="S-01 Branches I work at",
        responses={200: BranchSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        branches = branches_for_user(request.user.pk)
        return Response(BranchSerializer(branches, many=True).data)
