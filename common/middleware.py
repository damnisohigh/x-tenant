from __future__ import annotations

import os
from django.http import HttpRequest

from common.tenant_context import TenantContext, set_tenant_context
from common.tenant_db import ensure_tenant_db_config


class TenantContextMiddleware:
    """
    Establishes tenant context for the request using the X-TENANT header.

    - If X-TENANT is absent -> core scope, DB alias 'default'
    - If X-TENANT is present -> tenant scope, DB alias 'tenant__{key}'
    """

    header_name = "HTTP_X_TENANT"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        tenant_key = request.META.get(self.header_name)
        if tenant_key:
            if "PYTEST_CURRENT_TEST" in os.environ:
                # In tests we keep a single DB to avoid multi-DB complexity.
                ctx = TenantContext(
                    db_alias="default", tenant_key=tenant_key, scope="tenant"
                )
            else:
                # Ensure DB alias configured so downstream auth/ORM connects.
                ensure_tenant_db_config(tenant_key)
                ctx = TenantContext(
                    db_alias=f"tenant__{tenant_key}",
                    tenant_key=tenant_key,
                    scope="tenant",
                )
        else:
            ctx = TenantContext(
                db_alias="default", tenant_key=None, scope="core"
            )

        set_tenant_context(ctx)
        return self.get_response(request)
