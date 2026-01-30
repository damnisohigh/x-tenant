from __future__ import annotations

from common.tenant_context import get_tenant_context


class TenantRouter:
    """
    Routes all ORM operations to DB selected by TenantContextMiddleware.

    We keep it simple: everything (auth_user, Organization, etc.)
    goes to the current context DB alias.
    """

    def db_for_read(self, model, **hints):
        return get_tenant_context().db_alias

    def db_for_write(self, model, **hints):
        return get_tenant_context().db_alias

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # When provisioning tenant DB we explicitly run migrate against alias,
        # so allow all apps to migrate on any DB.
        return True
