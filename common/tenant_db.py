from __future__ import annotations

from dataclasses import dataclass
import os

from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.utils import ProgrammingError


@dataclass(frozen=True)
class TenantDbInfo:
    tenant_key: str
    db_alias: str
    db_name: str


def tenant_db_name(tenant_key: str) -> str:
    safe = tenant_key.lower().replace("-", "_")
    return f"xtenant_tenant_{safe}"


def tenant_db_alias(tenant_key: str) -> str:
    return f"tenant__{tenant_key}"


def ensure_tenant_db_config(
    tenant_key: str, *, db_name: str | None = None
) -> TenantDbInfo:
    alias = tenant_db_alias(tenant_key)
    name = db_name or tenant_db_name(tenant_key)

    if alias not in settings.DATABASES:
        cfg = dict(settings.TENANT_DB)
        cfg.update(
            {
                "NAME": name,
                "ATOMIC_REQUESTS": False,
                "AUTOCOMMIT": True,
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": False,
                "OPTIONS": {},
                "TIME_ZONE": None,
            }
        )
        settings.DATABASES[alias] = cfg

    return TenantDbInfo(tenant_key=tenant_key, db_alias=alias, db_name=name)


def create_database_if_missing(db_name: str) -> None:
    """
    CREATE DATABASE must be executed outside a transaction.
    We use the core connection to do it; the core DB user must have CREATEDB.
    """
    if settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
        # sqlite uses file-based DBs; no server-side provisioning.
        return

    conn = connections["default"]
    old_autocommit = conn.get_autocommit()
    conn.set_autocommit(True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", [db_name]
            )
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.set_autocommit(old_autocommit)


def provision_tenant_database(
    tenant_key: str, *, db_name: str | None = None
) -> TenantDbInfo:
    if "PYTEST_CURRENT_TEST" in os.environ:
        # In tests we keep everything in default DB; we still want the
        # tenant_key metadata but no physical DB provisioning.
        default_name = settings.DATABASES["default"]["NAME"]
        return TenantDbInfo(
            tenant_key=tenant_key,
            db_alias="default",
            db_name=str(default_name),
        )

    info = ensure_tenant_db_config(tenant_key, db_name=db_name)
    create_database_if_missing(info.db_name)

    # Ensure Django can connect
    try:
        connections[info.db_alias].ensure_connection()
    except ProgrammingError:
        # In case DB exists but is not ready; re-raise for now.
        raise

    # Apply migrations to the tenant DB (auth tables etc.)
    call_command(
        "migrate", database=info.db_alias, interactive=False, verbosity=0
    )
    return info
