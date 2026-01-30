from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantContext:
    db_alias: str
    tenant_key: Optional[str] = None  # value from X-TENANT (e.g. org slug)
    scope: str = "core"  # "core" | "tenant"


_ctx: contextvars.ContextVar[TenantContext] = contextvars.ContextVar(
    "tenant_context",
    default=TenantContext(db_alias="default", tenant_key=None, scope="core"),
)


def get_tenant_context() -> TenantContext:
    return _ctx.get()


def set_tenant_context(ctx: TenantContext) -> None:
    _ctx.set(ctx)
