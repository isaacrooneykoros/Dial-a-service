"""Invitations: the console side (A-41, minimal in M1) and X-14 accept, plus the first PIN."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.cookies import set_refresh_cookie
from apps.accounts.api.permissions import IsOwnerOrManager
from apps.accounts.api.serializers import (
    CodeSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    LoginResponseSerializer,
    MeSerializer,
    MessageSerializer,
    PinSerializer,
    PublicInvitationSerializer,
    SetupTokenSerializer,
)
from apps.accounts.api.throttling import CodeCheckIPThrottle, CodeSendIPThrottle
from apps.accounts.api.views import ERROR, code_failure, send_refused
from apps.accounts.models import ROLE_LABELS, Invitation
from apps.accounts.services import invitations, pins
from apps.core.api.errors import envelope
from apps.core.tenant_context import get_current_business_id
from apps.tenancy.selectors import support_contact

INVITATION_MESSAGES = {
    "role_not_allowed": _("You can invite managers, accountants and staff."),
    "already_registered": _("This number already has an account here."),
    "unknown_branch": _("Choose branches from this business."),
    "branch_required": _("Choose at least one branch."),
    "not_your_branch": _("You can only invite people to your own branches."),
    "invitation_closed": _("This invitation has already been used or cancelled."),
}

PIN_MESSAGES = {
    "pin_format": _("Enter 4 digits."),
    "pin_too_common": _("That PIN is too easy to guess. Choose another."),
    "pin_not_for_role": _("PINs are for people who use the counter devices."),
    "pin_already_set": _("You already have a PIN."),
}


def invitation_error(exc: invitations.InvitationError) -> Response:
    message = INVITATION_MESSAGES.get(exc.code, "")
    if exc.code in ("invitation_expired", "not_found"):
        return expired_response()
    fields = {exc.field: [message]} if exc.field else None
    status_code = 409 if exc.code in ("already_registered", "invitation_closed") else 400
    return Response(envelope(exc.code, message, fields), status=status_code)


def expired_response() -> Response:
    business_name, _phone = support_contact(get_current_business_id())
    # X-14: "Ask {business} to send a new invitation"
    message = _("Ask %(business)s to send a new invitation") % {"business": business_name}
    return Response(envelope("invitation_expired", message), status=410)


# --- Console (A-41, minimal form in M1) --------------------------------------------


class InvitationListCreateView(generics.ListAPIView[Invitation]):
    permission_classes = [IsOwnerOrManager]
    serializer_class = InvitationSerializer

    def get_queryset(self) -> QuerySet[Invitation]:
        return Invitation.objects.filter(
            accepted_at__isnull=True, cancelled_at__isnull=True, expires_at__gt=timezone.now()
        )

    @extend_schema(
        operation_id="console_invitations_create",
        summary="A-41 Invite a person",
        request=InvitationCreateSerializer,
        responses={201: InvitationSerializer, **ERROR},
    )
    def post(self, request: Request) -> Response:
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        details = invitations.InvitationDetails(
            phone=data["phone"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            role=data["role"],
            branch_ids=data["branch_ids"],
            can_accept_cash=data["rights"].get("accept_cash", False),
            can_give_discounts=data["rights"].get("give_discounts", False),
            can_correct_prices=data["rights"].get("correct_prices", False),
        )
        try:
            invitation = invitations.invite(request.user, details, request=request)
        except invitations.InvitationError as exc:
            return invitation_error(exc)
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class InvitationActionView(APIView):
    permission_classes = [IsOwnerOrManager]

    def act(self, request: Request, pk: UUID, action: str) -> Response:
        invitation = get_object_or_404(Invitation.objects.select_for_update(), pk=pk)
        try:
            if action == "resend":
                invitations.resend(invitation, actor=request.user, request=request)
            else:
                invitations.cancel(invitation, actor=request.user, request=request)
        except invitations.InvitationError as exc:
            return invitation_error(exc)
        return Response(InvitationSerializer(invitation).data)


class InvitationResendView(InvitationActionView):
    @extend_schema(
        operation_id="console_invitations_resend",
        summary="A-41 Resend an invitation (new link, 7 more days)",
        request=None,
        responses={200: InvitationSerializer, **ERROR},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        return self.act(request, pk, "resend")


class InvitationCancelView(InvitationActionView):
    @extend_schema(
        operation_id="console_invitations_cancel",
        summary="A-41 Cancel an invitation",
        request=None,
        responses={200: InvitationSerializer, **ERROR},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        return self.act(request, pk, "cancel")


# --- X-14 Accept invitation (public) -----------------------------------------------


class PublicInvitationMixin:
    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]

    def load(self, token: str) -> Invitation | Response:
        """The usable invitation behind ``token``, or the error response to return."""
        invitation, problem = invitations.open_invitation(token)
        if invitation is None:
            return Response(envelope("not_found", _("We couldn't find that")), status=404)
        if problem:
            return expired_response()
        return invitation


class PublicInvitationView(PublicInvitationMixin, APIView):
    @extend_schema(
        operation_id="auth_invitation_detail",
        summary="X-14 What this invitation is",
        responses={200: PublicInvitationSerializer, **ERROR},
        auth=[],
    )
    def get(self, request: Request, token: str) -> Response:
        invitation = self.load(token)
        if isinstance(invitation, Response):
            return invitation
        business_name, _phone = support_contact(get_current_business_id())
        return Response(
            {
                "business_name": business_name,
                "role": invitation.role,
                "role_label": ROLE_LABELS[invitation.role],
                "first_name": invitation.first_name,
                "phone": invitation.phone,
            }
        )


class InvitationSendCodeView(PublicInvitationMixin, APIView):
    throttle_classes = [CodeSendIPThrottle]

    @extend_schema(
        operation_id="auth_invitation_send_code",
        summary="X-14 Send code",
        request=None,
        responses={200: MessageSerializer, **ERROR},
        auth=[],
    )
    def post(self, request: Request, token: str) -> Response:
        invitation = self.load(token)
        if isinstance(invitation, Response):
            return invitation
        result = invitations.send_code(invitation)
        if not result.ok:
            return send_refused(result)
        return Response({"message": _("We've sent a code to your phone")})


class InvitationVerifyView(PublicInvitationMixin, APIView):
    throttle_classes = [CodeCheckIPThrottle]

    @extend_schema(
        operation_id="auth_invitation_verify",
        summary="X-12 in the invitation flow: check the code",
        request=CodeSerializer,
        responses={200: SetupTokenSerializer, **ERROR},
        auth=[],
    )
    def post(self, request: Request, token: str) -> Response:
        invitation = self.load(token)
        if isinstance(invitation, Response):
            return invitation
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = invitations.verify_code(invitation, serializer.validated_data["code"])
        if not result.ok:
            return code_failure(result)
        return Response({"setup_token": result.grant})


class InvitationAcceptView(APIView):
    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]
    throttle_classes = [CodeCheckIPThrottle]

    @extend_schema(
        operation_id="auth_invitation_accept",
        summary="X-13 in the invitation flow: set a password; creates the account and signs in",
        request=InvitationAcceptSerializer,
        responses={201: LoginResponseSerializer, **ERROR},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            signed_in = invitations.accept(request, **serializer.validated_data)
        except invitations.InvitationError as exc:
            return invitation_error(exc)
        body = {"access": signed_in.access, "user": MeSerializer(signed_in.user).data}
        response = Response(body, status=status.HTTP_201_CREATED)
        set_refresh_cookie(response, signed_in.refresh)
        return response


# --- First PIN (end of the X-14 flow) ---------------------------------------------------


class MyPinView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="me_pin_set",
        summary="Choose my 4-digit PIN for counter devices (first time)",
        request=PinSerializer,
        responses={204: None, **ERROR},
    )
    def post(self, request: Request) -> Response:
        serializer = PinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: Any = request.user
        try:
            pins.set_first_pin(user, serializer.validated_data["pin"], request=request)
        except pins.PinError as exc:
            message = PIN_MESSAGES[exc.code]
            status_code = 409 if exc.code == "pin_already_set" else 400
            if exc.code == "pin_not_for_role":
                status_code = 403
            return Response(envelope(exc.code, message, {"pin": [message]}), status=status_code)
        return Response(status=status.HTTP_204_NO_CONTENT)
