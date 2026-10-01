"""Reusable migration operations for tenant isolation (ADR-0001 section 4).

Policies are never hand-written per table. Every tenant table gets them through
these operations, and tests/test_tenancy_contract.py checks that none is missing.

    operations = [
        migrations.CreateModel(name="Thing", ...),
        EnableTenantRLS("thing"),
        MakeAppendOnly("thing"),      # only for logs that must never change
    ]
"""

from typing import Any

from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.operations.base import Operation
from django.db.migrations.state import ProjectState

POLICY_NAME = "tenant_isolation"
# NULLIF: once a connection has used the setting, Postgres reports it as ''
# rather than NULL; both mean "no business", which matches no rows.
CURRENT_BUSINESS_SQL = "NULLIF(current_setting('app.business_id', true), '')::uuid"
APP_ROLES = ("dial_app", "dial_platform")


def _table(app_label: str, model_name: str, state: ProjectState, editor: Any) -> str:
    model = state.apps.get_model(app_label, model_name)
    quoted: str = editor.quote_name(model._meta.db_table)
    return quoted


class EnableTenantRLS(Operation):
    """ENABLE and FORCE row-level security plus the tenant_isolation policy."""

    reversible = True
    reduces_to_sql = True

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name.lower()

    def deconstruct(self) -> tuple[str, list[str], dict[str, Any]]:
        return (self.__class__.__qualname__, [self.model_name], {})

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        """Database-only operation: the model state doesn't change."""

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table = _table(app_label, self.model_name, to_state, schema_editor)
        schema_editor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        schema_editor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        schema_editor.execute(
            f"CREATE POLICY {POLICY_NAME} ON {table} "
            f"USING (business_id = {CURRENT_BUSINESS_SQL}) "
            f"WITH CHECK (business_id = {CURRENT_BUSINESS_SQL})"
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table = _table(app_label, self.model_name, from_state, schema_editor)
        schema_editor.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    def describe(self) -> str:
        return f"Enable tenant row-level security on {self.model_name}"

    @property
    def migration_name_fragment(self) -> str:
        return f"rls_{self.model_name}"


class MakeAppendOnly(Operation):
    """Revoke UPDATE and DELETE from the app roles: rows can be added, never changed.

    Used for audit logs, consent records, status events, ledger entries and SMS
    transactions (CLAUDE.md section 11: never edit or delete them).
    """

    reversible = True
    reduces_to_sql = True

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name.lower()

    def deconstruct(self) -> tuple[str, list[str], dict[str, Any]]:
        return (self.__class__.__qualname__, [self.model_name], {})

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        """Database-only operation: the model state doesn't change."""

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table = _table(app_label, self.model_name, to_state, schema_editor)
        schema_editor.execute(f"REVOKE UPDATE, DELETE ON {table} FROM {', '.join(APP_ROLES)}")

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table = _table(app_label, self.model_name, from_state, schema_editor)
        schema_editor.execute(f"GRANT UPDATE, DELETE ON {table} TO {', '.join(APP_ROLES)}")

    def describe(self) -> str:
        return f"Make {self.model_name} append-only for the app roles"

    @property
    def migration_name_fragment(self) -> str:
        return f"append_only_{self.model_name}"
