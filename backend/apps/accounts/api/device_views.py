"""Registered counter devices: S-02 register, X-15 switch user, and A-42 in the console."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.cookies import (
    clear_refresh_cookie,
    read_device_cookie,
    set_device_cookie,
    set_refresh_cookie,
)
from apps.accounts.api.permissions import IsOwnerOrManager
from apps.accounts.api.serializers import (
    ConsoleDeviceSerializer,
    CurrentDeviceSerializer,
    DeviceRegisterSerializer,
    DeviceSerializer,
    LoginResponseSerializer,
    MeSerializer,
    PinSwitchSerializer,
    SessionSerializer,
)
from apps.accounts.api.throttling import PinSwitchIPThrottle
from apps.accounts.api.views import ERROR
from apps.accounts.models import Device, UserSession
from apps.accounts.services import console_access, devices, pin_switch
from apps.core.api.errors import envelope

DEVICE_MESSAGES = {
    "not_allowed": _("Only a manager or the owner can register a device."),
    "unknown_branch": _("Choose a branch of this business."),
    "not_your_branch": _("You can only register devices for your own branches."),
}


class DeviceRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="staff_devices_register",
        summary="S-02 Register this device (signs you out of it)",
        request=DeviceRegisterSerializer,
        responses={201: DeviceSerializer, **ERROR},
    )
    def post(self, request: Request) -> Response:
        serializer = DeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = request.auth if isinstance(request.auth, UserSession) else None
        try:
            registered = devices.register_device(
                request.user, session=session, request=request, **serializer.validated_data
            )
        except devices.DeviceError as exc:
            message = DEVICE_MESSAGES[exc.code]
            fields = {exc.field: [message]} if exc.field else None
            status_code = 403 if exc.code == "not_allowed" else 400
            return Response(envelope(exc.code, message, fields), status=status_code)
        response = Response(
            DeviceSerializer(registered.device).data, status=status.HTTP_201_CREATED
        )
        set_device_cookie(response, registered.token)
        clear_refresh_cookie(response)
        return response


class CurrentDeviceView(APIView):
    """Identified by the das_device cookie, not by a signed-in person."""

    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="devices_current",
        summary="X-15 This device, its branch, lock state and who can switch in",
        responses={200: CurrentDeviceSerializer, **ERROR},
        auth=[],
    )
    def get(self, request: Request) -> Response:
        device = devices.device_from_token(read_device_cookie(request._request))
        if device is None:
            return Response(envelope("not_found", _("We couldn't find that")), status=404)
        devices.touch(device)
        body = {
            "device": device,
            "locked": device.status == Device.Status.LOCKED,
            "roster": devices.roster(device),
        }
        return Response(CurrentDeviceSerializer(body).data)


PIN_SWITCH_MESSAGES = {
    "wrong_pin": _("That PIN isn't right."),
    "device_locked": _("This device is locked. Ask a manager to sign in on it to unlock it."),
}


class PinSwitchView(APIView):
    """X-15: identified by the das_device cookie; a PIN signs a person in on it."""

    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]
    throttle_classes = [PinSwitchIPThrottle]

    @extend_schema(
        operation_id="auth_pin_switch",
        summary="X-15 Switch user with a PIN on a registered device",
        request=PinSwitchSerializer,
        responses={200: LoginResponseSerializer, **ERROR},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        device = devices.device_from_token(read_device_cookie(request._request))
        if device is None:
            return Response(envelope("not_found", _("We couldn't find that")), status=404)
        serializer = PinSwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = pin_switch.switch_user(device, request=request, **serializer.validated_data)
        if not result.ok or result.signed_in is None:
            # Returned, not raised: the wrong PIN must still count towards the lock.
            body = envelope(
                result.reason,
                PIN_SWITCH_MESSAGES[result.reason],
                attempts_left=result.attempts_left,
            )
            return Response(body, status=403 if result.reason == "device_locked" else 400)
        signed_in = result.signed_in
        response = Response({"access": signed_in.access, "user": MeSerializer(signed_in.user).data})
        set_refresh_cookie(response, signed_in.refresh)
        return response


# --- A-42 in the console: sessions and devices -------------------------------------------


class ConsoleSessionsView(generics.ListAPIView[UserSession]):
    permission_classes = [IsOwnerOrManager]
    serializer_class = SessionSerializer

    def get_queryset(self) -> QuerySet[UserSession]:
        return console_access.visible_sessions(self.request.user)

    def get_serializer_context(self) -> dict[str, Any]:
        context: dict[str, Any] = super().get_serializer_context()
        auth_session = self.request.auth
        context["current_session_id"] = getattr(auth_session, "pk", None)
        return context

    @extend_schema(operation_id="console_sessions_list", summary="A-42 Signed-in sessions")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)


class ConsoleSessionSignOutView(APIView):
    permission_classes = [IsOwnerOrManager]

    @extend_schema(
        operation_id="console_sessions_sign_out",
        summary="A-42 Sign a session out",
        request=None,
        responses={204: None, **ERROR},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        session = get_object_or_404(console_access.visible_sessions(request.user), pk=pk)
        console_access.sign_out_session(session, viewer=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConsoleDevicesView(generics.ListAPIView[Device]):
    permission_classes = [IsOwnerOrManager]
    serializer_class = ConsoleDeviceSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[Device]:
        return console_access.visible_devices(self.request.user)

    @extend_schema(operation_id="console_devices_list", summary="A-42 Registered devices")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)


class ConsoleDeviceRemoveView(APIView):
    permission_classes = [IsOwnerOrManager]

    @extend_schema(
        operation_id="console_devices_remove",
        summary="A-42 Remove a device (ends every session on it)",
        request=None,
        responses={204: None, **ERROR},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        device = get_object_or_404(
            console_access.visible_devices(request.user).select_for_update(), pk=pk
        )
        console_access.remove_device(device, viewer=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
