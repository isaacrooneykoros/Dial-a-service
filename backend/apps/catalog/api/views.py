"""Console catalogue API: /api/v1/console/catalog/... (M2 T06, for A-30 in M5).

Owners and managers only (D-60). Views are thin: shapes are checked by the
serializers, rules by apps/catalog/services.py. A refused change comes back as the
error envelope with the reason on the field it's about.
"""

from dataclasses import asdict
from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsOwnerOrManager
from apps.catalog import imports, selectors, services
from apps.catalog.api import serializers as s
from apps.catalog.models import PriceModifier, Service, ServiceCategory, ServicePrice
from apps.catalog.services import CatalogError
from apps.core.api.errors import envelope
from apps.core.api.pagination import DefaultCursorPagination

ERRORS = {
    400: OpenApiResponse(description="Error envelope"),
    403: OpenApiResponse(description="Error envelope"),
    404: OpenApiResponse(description="Error envelope"),
    409: OpenApiResponse(description="Error envelope"),
}

CATALOG_MESSAGES = {
    "name_required": _("Enter a name."),
    "duplicate_name": _("That name is already used. Choose another."),
    "bad_code": _("Use lowercase letters, numbers and hyphens, like wash-fold."),
    "duplicate_code": _("Another service already uses that code."),
    "bad_pricing_model": _("Choose per kg, per item or flat."),
    "bad_unit": _("Choose kg, item, pair or set."),
    "unit_mismatch": _("Per kg services use kg; per item and flat services use item, pair or set."),
    "pricing_model_locked": _(
        "This service already has prices, so how it's priced can't change. "
        "Create a new service instead."
    ),
    "needs_price": _("Set a price before switching this service on."),
    "duplicate_service": _("Each service can appear only once."),
    "unknown_service": _("Choose services from this price list."),
    "unknown_category": _("Choose a category from this price list."),
    "bad_amount": _("Enter a valid amount, to the cent."),
    "minimum_per_kg_only": _("A minimum charge is only for per kg services."),
    "bad_start": _("Give the start time with its time zone."),
    "starts_in_past": _("A new price can start now or later, not in the past."),
    "unknown_branch": _("Choose a branch of this business."),
    "price_conflict": _("This price was changed at the same moment. Refresh and try again."),
    "percent_or_amount": _("Give a percentage or an amount, not both."),
    "bad_percent": _("Enter a percentage above 0 and up to 999.99, with at most 2 decimals."),
    "bad_kind": _("Choose Express or Preference."),
    "applies_to_all": _("This modifier applies to all services, so don't choose a list."),
}


def catalog_error(exc: CatalogError) -> Response:
    message = str(CATALOG_MESSAGES[exc.code])
    fields = {exc.field: [message]} if exc.field else None
    status_code = 409 if exc.code == "price_conflict" else 400
    return Response(envelope(exc.code, message, fields), status=status_code)


def category_or_error(category_id: UUID) -> ServiceCategory:
    category: ServiceCategory | None = ServiceCategory.objects.filter(pk=category_id).first()
    if category is None:
        raise CatalogError("unknown_category", "category_id")
    return category


def service_data(service: Service) -> dict[str, Any]:
    return {**service.__dict__, "current_price": selectors.price_at(service.pk)}


def modifier_data(modifier: PriceModifier) -> dict[str, Any]:
    ids = selectors.modifier_service_ids(modifier)
    return {**modifier.__dict__, "service_ids": sorted(ids) if ids is not None else []}


class Console(APIView):
    permission_classes = [IsOwnerOrManager]


# --- Categories ---------------------------------------------------------------------------


class CategoriesView(Console):
    @extend_schema(
        operation_id="console_catalog_categories_list",
        summary="A-30 Categories, in price-list order",
        responses={200: s.CategorySerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        categories = ServiceCategory.objects.order_by("position", "name_en")
        return Response(s.CategorySerializer(categories, many=True).data)

    @extend_schema(
        operation_id="console_catalog_categories_create",
        summary="A-30 Add a category",
        request=s.CategorySerializer,
        responses={201: s.CategorySerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        data = s.CategorySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            category = services.create_category(**data.validated_data, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.CategorySerializer(category).data, status=status.HTTP_201_CREATED)


class CategoryUpdateView(Console):
    @extend_schema(
        operation_id="console_catalog_categories_update",
        summary="A-30 Rename a category, or switch it on or off",
        request=s.CategoryUpdateSerializer,
        responses={200: s.CategorySerializer, **ERRORS},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        category = get_object_or_404(ServiceCategory, pk=pk)
        data = s.CategoryUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.update_category(category, **data.validated_data, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.CategorySerializer(category).data)


# --- Services -----------------------------------------------------------------------------


class ServicesView(Console):
    @extend_schema(
        operation_id="console_catalog_services_list",
        summary="A-30 Services with their current business-wide price",
        responses={200: s.ServiceSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        rows = Service.objects.order_by("category__position", "position", "name_en")
        return Response(s.ServiceSerializer([service_data(x) for x in rows], many=True).data)

    @extend_schema(
        operation_id="console_catalog_services_create",
        summary="A-30 Add a service (switched off until priced)",
        request=s.ServiceCreateSerializer,
        responses={201: s.ServiceSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        data = s.ServiceCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        try:
            category = category_or_error(values.pop("category_id"))
            service = services.create_service(category=category, **values, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.ServiceSerializer(service_data(service)).data, status=201)


class ServiceUpdateView(Console):
    @extend_schema(
        operation_id="console_catalog_services_update",
        summary="A-30 Rename or move a service; how it's priced only until it has a price",
        request=s.ServiceUpdateSerializer,
        responses={200: s.ServiceSerializer, **ERRORS},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        service = get_object_or_404(Service, pk=pk)
        data = s.ServiceUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        try:
            if "category_id" in values:
                values["category"] = category_or_error(values.pop("category_id"))
            services.update_service(service, **values, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.ServiceSerializer(service_data(service)).data)


class ServiceActivationView(Console):
    active = True

    def post(self, request: Request, pk: UUID) -> Response:
        service = get_object_or_404(Service, pk=pk)
        try:
            services.set_service_active(service, self.active, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.ServiceSerializer(service_data(service)).data)


class ServiceActivateView(ServiceActivationView):
    @extend_schema(
        operation_id="console_catalog_services_activate",
        summary="A-30 Switch a service on (needs a current price)",
        request=None,
        responses={200: s.ServiceSerializer, **ERRORS},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        return super().post(request, pk)


class ServiceDeactivateView(ServiceActivationView):
    active = False

    @extend_schema(
        operation_id="console_catalog_services_deactivate",
        summary="A-30 Switch a service off (never deleted)",
        request=None,
        responses={200: s.ServiceSerializer, **ERRORS},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        return super().post(request, pk)


class ServicesReorderView(Console):
    @extend_schema(
        operation_id="console_catalog_services_reorder",
        summary="A-30 Order the services (the staff app's quick-add buttons)",
        request=s.ReorderSerializer,
        responses={200: s.ServiceSerializer(many=True), **ERRORS},
    )
    def post(self, request: Request) -> Response:
        data = s.ReorderSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            ordered = services.reorder_services(data.validated_data["service_ids"], request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.ServiceSerializer([service_data(x) for x in ordered], many=True).data)


# --- Prices -------------------------------------------------------------------------------


class PriceVersionPagination(DefaultCursorPagination):
    ordering = "-effective_from"


class ServicePricesView(Console, generics.ListAPIView[ServicePrice]):
    serializer_class = s.PriceSerializer
    pagination_class = PriceVersionPagination

    def get_queryset(self) -> QuerySet[ServicePrice]:
        service = get_object_or_404(Service, pk=self.kwargs["pk"])
        return selectors.price_versions(
            service.pk, branch_id=self.request.query_params.get("branch_id")
        )

    @extend_schema(
        operation_id="console_catalog_prices_list",
        summary="A-30 Price versions, newest first (business-wide, or one branch's overrides)",
        parameters=[OpenApiParameter("branch_id", str, required=False)],
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="console_catalog_prices_set",
        summary="A-30 Set a price from now or a later time (a new version)",
        request=s.PriceCreateSerializer,
        responses={201: s.PriceSerializer, **ERRORS},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        service = get_object_or_404(Service, pk=pk)
        data = s.PriceCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            price = services.set_price(service, **data.validated_data, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.PriceSerializer(price).data, status=status.HTTP_201_CREATED)


# --- Modifiers ----------------------------------------------------------------------------


class ModifiersView(Console):
    @extend_schema(
        operation_id="console_catalog_modifiers_list",
        summary="A-30 Modifiers (Express and chargeable preferences)",
        responses={200: s.ModifierSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        rows = PriceModifier.objects.order_by("position", "name_en")
        return Response(s.ModifierSerializer([modifier_data(m) for m in rows], many=True).data)

    @extend_schema(
        operation_id="console_catalog_modifiers_create",
        summary="A-30 Add a modifier: a percentage per line or an amount once per order",
        request=s.ModifierCreateSerializer,
        responses={201: s.ModifierSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        data = s.ModifierCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            modifier = services.create_modifier(**data.validated_data, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.ModifierSerializer(modifier_data(modifier)).data, status=201)


class ModifierUpdateView(Console):
    @extend_schema(
        operation_id="console_catalog_modifiers_update",
        summary="A-30 Change a modifier (applies to new quotes only)",
        request=s.ModifierUpdateSerializer,
        responses={200: s.ModifierSerializer, **ERRORS},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        modifier = get_object_or_404(PriceModifier, pk=pk)
        data = s.ModifierUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.update_modifier(modifier, **data.validated_data, request=request)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.ModifierSerializer(modifier_data(modifier)).data)


# --- CSV import (A-31) ----------------------------------------------------------------------

ROW_MESSAGES = {
    "service_required": _("Give the service's name or code."),
    "duplicate_row": _("This service is already in the file on another line."),
    "bad_pricing_model": _("Write per_kg, per_item or flat."),
    "price_amount_has_comma": _("Write prices without commas, like 1200.00."),
    "price_bad_amount": _("Write the price as a number above 0, like 120 or 120.50."),
    "minimum_amount_has_comma": _("Write the minimum without commas, like 500.00."),
    "minimum_bad_amount": _(
        "Write the minimum as a number, like 500 or 500.00, or leave it empty."
    ),
    "minimum_per_kg_only": _("A minimum charge is only for per kg services."),
    "ambiguous_service": _("Several services have this name. Use the service's code instead."),
    "pricing_model_differs": _(
        "This service is priced differently in your price list. Create a new service for it."
    ),
    "unit_differs": _("This service uses a different unit in your price list."),
    "unit_mismatch": _("Per kg services use kg; others use item, pair or set."),
    "category_required": _("Give a category for this new service."),
}

FILE_MESSAGES = {
    "too_big": _("The file is too big. Import at most 1 MB at a time."),
    "empty": _("The file has no prices in it."),
    "missing_columns": _("The file needs these columns: %(columns)s."),
    "too_many_rows": _("Import at most %(max_rows)d services at a time."),
    "unreadable": _("We couldn't read this file. Save it as CSV and try again."),
    "changed_since_preview": _(
        "The price list changed since you previewed this file. Preview it again."
    ),
    "has_invalid_rows": _("Fix the %(count)d rows marked invalid, then preview again."),
}


def import_error(exc: imports.CatalogImportError) -> Response:
    detail = dict(exc.detail)
    if "columns" in detail:
        detail["columns"] = ", ".join(detail["columns"])
    template = str(FILE_MESSAGES[exc.code])
    message = template % detail if detail else template
    status_code = 409 if exc.code == "changed_since_preview" else 400
    return Response(envelope(exc.code, message, {"csv": [message]}), status=status_code)


def preview_data(preview: imports.Preview) -> dict[str, Any]:
    rows = [
        {**asdict(row), "message": str(ROW_MESSAGES[row.problem]) if row.problem else ""}
        for row in preview.rows
    ]
    return {"rows": rows, "counts": preview.counts, "fingerprint": preview.fingerprint}


class ImportTemplateView(Console):
    @extend_schema(
        operation_id="console_catalog_import_template",
        summary="A-31 The CSV template: your current price list, ready to edit",
        responses={(200, "text/csv"): OpenApiTypes.STR},
    )
    def get(self, request: Request) -> HttpResponse:
        response = HttpResponse(imports.template_csv(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="price-list.csv"'
        return response


class ImportPreviewView(Console):
    @extend_schema(
        operation_id="console_catalog_import_preview",
        summary="A-31 Preview a CSV import: each row new, changed, unchanged or invalid",
        request=s.ImportPreviewRequestSerializer,
        responses={200: s.ImportPreviewSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        data = s.ImportPreviewRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            preview = imports.preview(data.validated_data["csv"])
        except imports.CatalogImportError as exc:
            return import_error(exc)
        return Response(s.ImportPreviewSerializer(preview_data(preview)).data)


class ImportApplyView(Console):
    @extend_schema(
        operation_id="console_catalog_import_apply",
        summary="A-31 Apply a previewed import as new price versions (all or nothing)",
        request=s.ImportApplyRequestSerializer,
        responses={200: s.ImportPreviewSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        data = s.ImportApplyRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            applied = imports.apply(
                data.validated_data["csv"],
                fingerprint=data.validated_data["fingerprint"],
                effective_from=data.validated_data["effective_from"],
                request=request,
            )
        except imports.CatalogImportError as exc:
            return import_error(exc)
        except CatalogError as exc:
            return catalog_error(exc)
        return Response(s.ImportPreviewSerializer(preview_data(applied)).data)
