"""POST /api/v1/quotes: price an order without saving anything (M2 T08).

For the people at the counter in M2: owners, managers and staff. The same endpoint
serves S-14's live preview (M3), A-30's calculator (M5) and, from M9, customers.
"""

from dataclasses import asdict
from typing import Any

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.catalog import quotes
from apps.catalog.api import serializers as s
from apps.core.api.errors import envelope

QUOTE_ROLES = (Role.OWNER, Role.MANAGER, Role.STAFF)

QUOTE_MESSAGES = {
    "unknown_branch": _("Choose a branch of this business."),
    "unknown_service": _("Choose services from this price list."),
    "service_off": _("%(name)s is switched off, so it can't be priced."),
    "no_price": _("%(name)s has no price yet."),
    "unknown_modifier": _("Choose extras that are switched on in this price list."),
    "duplicate_modifier": _("Each extra can be chosen once."),
    "no_discount_right": _("You don't have the right to give discounts."),
    "discount_reason_required": _("Give a reason for the discount."),
    "discount_over_cap": _("That's more than the largest discount this business allows."),
    "bad_discount": _("Give the discount as a percentage or an amount above zero."),
    "bad_quantity": _(
        "Enter a weight from 0.01 kg (2 decimals), a whole number of items, or 1 for flat prices."
    ),
    "no_lines": _("Add at least one service."),
    "currency_mismatch": _("These prices can't be combined. Contact support."),
    "bad_vat_rate": _("This business's VAT rate is set wrongly. Check the settings."),
    "bad_modifier": _("One of these extras is set up wrongly. Check the price list."),
}


class CanQuote(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role in QUOTE_ROLES)


def quote_error(exc: quotes.QuoteError) -> Response:
    template = str(QUOTE_MESSAGES.get(exc.code, QUOTE_MESSAGES["no_lines"]))
    message = template % exc.detail if exc.detail else template
    fields = {exc.field: [message]} if exc.field else None
    return Response(envelope(exc.code, message, fields), status=400)


def quote_data(result: quotes.QuoteResult) -> dict[str, Any]:
    data = asdict(result.quote)
    for line in data["lines"]:
        service = result.services[line["service_id"]]
        line["name_en"], line["name_sw"] = service.name_en, service.name_sw
    return data


class QuoteView(APIView):
    permission_classes = [CanQuote]

    @extend_schema(
        operation_id="quotes_create",
        summary="Price an order (S-14 preview, A-30 calculator); saves nothing",
        request=s.QuoteRequestSerializer,
        responses={
            200: s.QuoteSerializer,
            400: OpenApiResponse(description="Error envelope"),
            403: OpenApiResponse(description="Error envelope"),
        },
    )
    def post(self, request: Request) -> Response:
        data = s.QuoteRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        discount = values["discount"]
        try:
            result = quotes.build_quote(
                [
                    quotes.QuoteLine(line["service_id"], line["quantity"])
                    for line in values["lines"]
                ],
                user=request.user,
                branch_id=values["branch_id"],
                modifier_ids=values["modifier_ids"],
                discount=quotes.DiscountRequest(**discount) if discount else None,
            )
        except quotes.QuoteError as exc:
            return quote_error(exc)
        return Response(s.QuoteSerializer(quote_data(result)).data)
