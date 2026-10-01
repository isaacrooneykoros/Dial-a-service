"""Every request belongs to one business, decided by its host (ADR-0001 sections 1 and 2).

TenantResolutionMiddleware: Host -> business through BusinessDomain (cached).
Unknown hosts get a 404 envelope before any view, session or authentication
code runs. Exempt paths (the health check) and the platform-admin host have no
business.

TenantTransactionMiddleware: wraps a business request in tenant_context(), so
the whole request is one transaction with app.business_id set locally. A 5xx
response rolls it back; a 4xx response a view *returns* is committed (some
failures must leave a trace, such as a wrong PIN counting towards a lock).
Errors raised through DRF are rolled back by apps/core/api/exceptions.py.
"""

from collections.abc import Callable

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponseBase

from apps.core.api.errors import error_json
from apps.core.tenant_context import tenant_context
from apps.tenancy.selectors import ResolvedBusiness, resolve_host
from apps.tenancy.validators import normalize_host

PLATFORM_ADMIN_SERVICE = "platform_admin"

GetResponse = Callable[[HttpRequest], HttpResponseBase]


class TenantResolutionMiddleware:
    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        request.business = None  # type: ignore[attr-defined]

        if request.path_info in settings.TENANCY_EXEMPT_PATHS:
            return self.get_response(request)

        host = normalize_host(request.get_host())
        is_platform_service = settings.DJANGO_SERVICE == PLATFORM_ADMIN_SERVICE
        is_admin_host = host == settings.PLATFORM_ADMIN_HOST

        if is_platform_service or is_admin_host:
            # The platform-admin service serves only the admin host, which has
            # no business; the API service never serves the admin host.
            if is_platform_service and is_admin_host:
                return self.get_response(request)
            return error_json(request, 404, "not_found")

        business: ResolvedBusiness | None = resolve_host(host)
        if business is None:
            return error_json(request, 404, "not_found")
        request.business = business  # type: ignore[attr-defined]
        return self.get_response(request)


class TenantTransactionMiddleware:
    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        business: ResolvedBusiness | None = getattr(request, "business", None)
        if business is None:
            return self.get_response(request)

        with tenant_context(business.id):
            response = self.get_response(request)
            if response.status_code >= 500:
                # Django turned an exception into this response inside the
                # middleware chain; don't commit what the view half-did.
                transaction.set_rollback(True)
        return response
