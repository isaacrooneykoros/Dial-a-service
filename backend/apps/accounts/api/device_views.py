"""Registered counter devices: S-02 register, and the device X-15 runs on."""

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.cookies import clear_refresh_cookie, read_device_cookie, set_device_cookie
from apps.accounts.api.serializers import (
    CurrentDeviceSerializer,
    DeviceRegisterSerializer,
    DeviceSerializer,
)
from apps.accounts.api.views import ERROR
from apps.accounts.models import Device, UserSession
from apps.accounts.services import devices
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
