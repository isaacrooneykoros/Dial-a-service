"""Uploads (ADR-0004): ask for an upload URL, confirm the upload, and the local-only PUT."""

from typing import Any
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import uploads
from apps.core.api.errors import envelope, error_json
from apps.core.models import Upload
from apps.core.storage import LocalStorage, get_storage
from apps.core.tenant_context import get_current_business_id

ERROR = {
    400: OpenApiResponse(description="Error envelope"),
    409: OpenApiResponse(description="Error envelope"),
}

MESSAGES = {
    "unsupported_type": _("Send a photo (JPEG, PNG or WebP)."),
    "too_large": _("That photo is too big. Try again; the app makes it smaller."),
    "not_uploaded": _("The photo hasn't finished uploading. Try again."),
    "does_not_match": _("The photo didn't upload properly. Try again."),
}


class StartUploadSerializer(serializers.Serializer[Any]):
    content_type = serializers.CharField(max_length=50)
    size = serializers.IntegerField(min_value=1, help_text="Bytes.")


class UploadTicketSerializer(serializers.Serializer[Any]):
    upload_id = serializers.UUIDField()
    url = serializers.CharField(help_text="PUT the file here within 5 minutes.")
    method = serializers.CharField()
    headers = serializers.DictField(child=serializers.CharField())
    expires_at = serializers.DateTimeField()


class UploadSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    content_type = serializers.CharField()
    size = serializers.IntegerField()
    status = serializers.CharField()


def upload_error(exc: uploads.UploadError) -> Response:
    message = MESSAGES[exc.code]
    fields = {exc.field: [message]} if exc.field else None
    status_code = 400 if exc.field else 409
    return Response(envelope(exc.code, message, fields), status=status_code)


class StartUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="uploads_start",
        summary="Get a short-lived URL to upload a photo to private storage",
        request=StartUploadSerializer,
        responses={201: UploadTicketSerializer, **ERROR},
    )
    def post(self, request: Request) -> Response:
        serializer = StartUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ticket = uploads.start_upload(user=request.user, **serializer.validated_data)
        except uploads.UploadError as exc:
            return upload_error(exc)
        body = {
            "upload_id": ticket.upload.pk,
            "url": ticket.url,
            "method": "PUT",
            "headers": {"Content-Type": ticket.upload.content_type},
            "expires_at": ticket.expires_at,
        }
        return Response(UploadTicketSerializer(body).data, status=status.HTTP_201_CREATED)


class CompleteUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="uploads_complete",
        summary="Confirm the photo arrived",
        request=None,
        responses={200: UploadSerializer, **ERROR},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        upload = get_object_or_404(Upload.objects.select_for_update(), pk=pk)
        try:
            uploads.complete_upload(upload, user=request.user, request=request)
        except uploads.UploadError as exc:
            return upload_error(exc)
        return Response(UploadSerializer(upload).data)


@csrf_exempt
def local_upload_content(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Local adapter only: PUT the bytes here. The signed token is the only key, and it
    binds the upload, the business and a 5-minute expiry (ADR-0004)."""
    storage = get_storage()
    if request.method != "PUT" or not isinstance(storage, LocalStorage):
        return error_json(request, 404, "not_found")
    claims = storage.read_token(request.GET.get("token", ""))
    business_id = str(get_current_business_id())
    if claims is None or claims.get("upload") != str(pk) or claims.get("business") != business_id:
        return error_json(request, 404, "not_found")
    upload = Upload.objects.filter(pk=pk, status=Upload.Status.PENDING).first()
    if upload is None:
        return error_json(request, 404, "not_found")
    content = request.body
    content_type = request.content_type or ""
    if content_type != upload.content_type:
        return error_json(request, 400, "unsupported_type", MESSAGES["unsupported_type"])
    if len(content) > min(upload.size, settings.UPLOAD_MAX_BYTES):
        return error_json(request, 400, "too_large", MESSAGES["too_large"])
    storage.save(upload.key, content, content_type)
    return HttpResponse(status=200)
