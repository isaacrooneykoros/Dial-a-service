"""Test-only views for the tenancy middleware and the cross-business harness."""

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from tests.testapp.models import Widget


def whoami(request: HttpRequest) -> JsonResponse:
    with connection.cursor() as cursor:
        cursor.execute("SELECT NULLIF(current_setting('app.business_id', true), '')")
        row = cursor.fetchone()
    business = getattr(request, "business", None)
    return JsonResponse(
        {
            "business_id": str(business.id) if business else None,
            "db_business_id": row[0] if row else None,
            "in_transaction": connection.in_atomic_block,
        }
    )


def create_then_raise(request: HttpRequest) -> HttpResponse:
    Widget.objects.create(name="half-done")
    raise RuntimeError("view crashed after writing")


def create_then_503(request: HttpRequest) -> HttpResponse:
    Widget.objects.create(name="half-done")
    return HttpResponse(status=503)


def create_then_400(request: HttpRequest) -> HttpResponse:
    Widget.objects.create(name="kept")
    return HttpResponse(status=400)


def widget_detail(request: HttpRequest, pk: str) -> JsonResponse:
    """Correct: the scoped manager (and RLS) only see the current business."""
    widget = get_object_or_404(Widget.objects, pk=pk)
    return JsonResponse({"id": str(widget.pk), "name": widget.name})


def widget_detail_leaky_cache(request: HttpRequest, pk: str) -> JsonResponse:
    """Deliberately wrong: caches by id alone, not by business. RLS can't stop this."""
    key = f"leaky-widget:{pk}"
    data = cache.get(key)
    if data is None:
        widget = get_object_or_404(Widget.objects, pk=pk)
        data = {"id": str(widget.pk), "name": widget.name}
        cache.set(key, data, 60)
    return JsonResponse(data)
