"""Which models are allowed to exist without row-level security (ADR-0001 section 7).

tests/test_tenancy_contract.py walks every installed model. Each must be:

1. listed in GLOBAL_MODELS (shared by all businesses; no business column), or
2. a TenantModel whose table has RLS enabled and forced, with the
   tenant_isolation policy, or
3. listed in NULLABLE_TENANT_MODELS (business may be empty for platform
   rows) with the same policy.

Adding to these lists needs a reason, and for GLOBAL_MODELS a review: a global
table is readable by every business's requests.
"""

GLOBAL_MODELS: dict[str, str] = {
    "tenancy.business": "Host resolution must find the business before any is in context.",
    "tenancy.businessdomain": "Host resolution reads it before a business is in context.",
    "contenttypes.contenttype": "Django's model registry; holds no business data.",
    "auth.permission": "Django's permission catalogue; no business data, unused by the API.",
    "auth.group": "Django's groups; no business data, unused (roles are fixed per user).",
    "auth.group_permissions": "Link table between the two above; no business data.",
    "core.appversion": "Minimum and latest app versions; the same for every business (X-02).",
}

NULLABLE_TENANT_MODELS: dict[str, str] = {
    "accounts.user": "Platform staff have no business; their rows are invisible to dial_app.",
    "core.auditlog": "Platform actions (P-12) have no business; the platform service writes them.",
}
