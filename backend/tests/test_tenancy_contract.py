"""The tenancy contract (CLAUDE.md section 6.1, ADR-0001 section 7).

Every installed model must be either global (listed with a reason in
apps/tenancy/registry.py) or a tenant model whose table has row-level security
enabled and forced with the tenant_isolation policy. A new model that forgets
EnableTenantRLS fails this test, and so does any auto-created many-to-many
table (link tables must be explicit tenant models).
"""

import pytest
from django.apps import apps
from django.db import connection, models

from apps.core.db import POLICY_NAME
from apps.core.models import TenantModel
from apps.tenancy.registry import GLOBAL_MODELS, NULLABLE_TENANT_MODELS

pytestmark = pytest.mark.django_db


def label(model: type[models.Model]) -> str:
    return model._meta.label_lower


def checked_models() -> list[type[models.Model]]:
    return [
        model
        for model in apps.get_models(include_auto_created=True)
        if model._meta.managed and not model._meta.proxy
    ]


def rls_problems(table: str) -> list[str]:
    """What's wrong with a tenant table's row-level security, if anything."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = to_regclass(%s)",
            [table],
        )
        flags = cursor.fetchone()
        cursor.execute(
            "SELECT cmd, roles::text[], qual, with_check FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = %s AND policyname = %s",
            [table, POLICY_NAME],
        )
        policy = cursor.fetchone()

    if flags is None:
        return [f"{table}: table not found"]
    problems = []
    if not flags[0]:
        problems.append(f"{table}: row-level security is not enabled")
    if not flags[1]:
        problems.append(f"{table}: row-level security is not forced")
    if policy is None:
        return [*problems, f"{table}: no {POLICY_NAME} policy (use EnableTenantRLS)"]
    cmd, roles, qual, with_check = policy
    if cmd != "ALL" or roles != ["public"]:
        problems.append(f"{table}: policy must apply to ALL commands for all roles")
    for name, clause in (("USING", qual), ("WITH CHECK", with_check)):
        text = clause or ""
        if "business_id" not in text or "current_setting('app.business_id'" not in text:
            problems.append(f"{table}: {name} doesn't compare business_id with app.business_id")
        if "NULLIF" not in text:
            problems.append(f"{table}: {name} must treat '' as no business (NULLIF)")
    return problems


def contract_problems(model: type[models.Model]) -> list[str]:
    name = label(model)
    table = model._meta.db_table
    if name in GLOBAL_MODELS:
        if issubclass(model, TenantModel):
            return [f"{name}: a TenantModel can't be listed as global"]
        return []
    if name in NULLABLE_TENANT_MODELS:
        field = model._meta.get_field("business")
        if not (isinstance(field, models.ForeignKey) and field.null):
            return [f"{name}: listed as nullable-tenant but has no nullable business FK"]
        return rls_problems(table)
    if issubclass(model, TenantModel):
        return rls_problems(table)
    if model._meta.auto_created:
        return [f"{name}: auto-created many-to-many table; use an explicit TenantModel link"]
    return [f"{name}: neither a TenantModel nor listed in apps/tenancy/registry.py"]


def test_every_model_is_global_or_protected_by_rls() -> None:
    problems = [problem for model in checked_models() for problem in contract_problems(model)]
    assert not problems, "Tenancy contract broken:\n" + "\n".join(problems)


def test_registry_has_no_stale_entries() -> None:
    installed = {label(model) for model in checked_models()}
    stale = (set(GLOBAL_MODELS) | set(NULLABLE_TENANT_MODELS)) - installed
    assert not stale, f"Registry lists models that don't exist: {sorted(stale)}"


def test_registry_entries_have_reasons() -> None:
    for registry in (GLOBAL_MODELS, NULLABLE_TENANT_MODELS):
        assert all(reason.strip() for reason in registry.values())


def test_a_table_without_rls_is_reported() -> None:
    # django_content_type is global, so it has no RLS: checked as if it were a tenant table.
    problems = rls_problems("django_content_type")
    assert any("not enabled" in p for p in problems)
    assert any("no tenant_isolation policy" in p for p in problems)


def test_an_unregistered_plain_model_is_reported() -> None:
    class Stray(models.Model):
        class Meta:
            app_label = "testapp"
            managed = False

        def __str__(self) -> str:
            return "stray"

    assert contract_problems(Stray) == [
        "testapp.stray: neither a TenantModel nor listed in apps/tenancy/registry.py"
    ]


def test_tenant_tables_pass() -> None:
    assert rls_problems("testapp_widget") == []
    assert rls_problems("tenancy_businessbranding") == []
