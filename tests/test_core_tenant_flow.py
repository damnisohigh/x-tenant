import pytest
from rest_framework.test import APIClient

from core.models import Organization

pytestmark = pytest.mark.django_db(databases="__all__")


def auth_header(access_token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


def tenant_header(tenant_slug: str) -> dict:
    return {"HTTP_X_TENANT": tenant_slug}


def test_full_core_and_tenant_flow():
    client = APIClient()

    # 1. Register core user
    resp = client.post(
        "/api/auth/register",
        {
            "username": "owner",
            "email": "owner@example.com",
            "password": "secret123",
        },
        format="json",
    )
    assert resp.status_code == 201
    core_access = resp.data["tokens"]["access"]

    # 2. Login core user
    resp = client.post(
        "/api/auth/login",
        {"username": "owner", "password": "secret123"},
        format="json",
    )
    assert resp.status_code == 200
    assert "access" in resp.data["tokens"]

    # 3. Create organization (core context, no X-TENANT)
    resp = client.post(
        "/api/organizations",
        {"name": "Acme Corp"},
        format="json",
        **auth_header(core_access),
    )
    assert resp.status_code == 201
    org_slug = resp.data["slug"]

    # Organization exists in core DB
    assert Organization.objects.using("default").filter(slug=org_slug).exists()

    # 4. Tenant login as owner (X-TENANT header + same credentials)
    resp = client.post(
        "/api/auth/login",
        {"username": "owner", "password": "secret123"},
        format="json",
        **tenant_header(org_slug),
    )
    assert resp.status_code == 200
    tenant_tokens = resp.data["tokens"]
    tenant_access = tenant_tokens["access"]

    # 5. Tenant register a second user
    resp = client.post(
        "/api/auth/register",
        {
            "username": "member",
            "email": "m@example.com",
            "password": "secret123",
        },
        format="json",
        **tenant_header(org_slug),
    )
    assert resp.status_code == 201

    # 6. Tenant /users/me for owner
    resp = client.get(
        "/api/users/me",
        format="json",
        **tenant_header(org_slug),
        **auth_header(tenant_access),
    )
    assert resp.status_code == 200
    assert resp.data["username"] == "owner"

    # 7. Update profile in tenant context
    resp = client.put(
        "/api/users/me",
        {
            "email": "owner-new@example.com",
            "first_name": "Alice",
            "last_name": "Owner",
        },
        format="json",
        **tenant_header(org_slug),
        **auth_header(tenant_access),
    )
    assert resp.status_code == 200
    assert resp.data["email"] == "owner-new@example.com"
