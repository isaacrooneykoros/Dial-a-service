"""Test-only views for the tenancy middleware and the cross-business harness."""

from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse

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
