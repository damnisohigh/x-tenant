from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from common.tenant_context import get_tenant_context
from common.tenant_db import provision_tenant_database, tenant_db_name
from core.models import Organization
from core.serializers import (
    LoginSerializer,
    OrganizationCreateSerializer,
    RegisterSerializer,
    UserMeSerializer,
)
from core.services import get_organization_by_slug

User = get_user_model()


def _issue_tokens(*, user, scope: str, tenant: str | None = None) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["scope"] = scope
    if tenant:
        refresh["tenant"] = tenant

    access = refresh.access_token
    access["scope"] = scope
    if tenant:
        access["tenant"] = tenant

    return {"refresh": str(refresh), "access": str(access)}


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ctx = get_tenant_context()
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        data = ser.validated_data
        if ctx.scope == "core":
            user = User.objects.db_manager("default").create_user(
                username=data["username"],
                email=data.get("email", ""),
                password=data["password"],
            )
            tokens = _issue_tokens(user=user, scope="core")
            return Response(
                {"user_id": user.id, "tokens": tokens},
                status=status.HTTP_201_CREATED,
            )

        # tenant registration
        org = get_organization_by_slug(ctx.tenant_key or "")
        if not org:
            return Response(
                {"detail": "Unknown tenant."}, status=status.HTTP_404_NOT_FOUND
            )

        provision_tenant_database(org.slug, db_name=org.tenant_db_name)
        user = User.objects.db_manager(ctx.db_alias).create_user(
            username=data["username"],
            email=data.get("email", ""),
            password=data["password"],
        )
        tokens = _issue_tokens(user=user, scope="tenant", tenant=org.slug)
        return Response(
            {"user_id": user.id, "tokens": tokens},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ctx = get_tenant_context()
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if ctx.scope == "tenant":
            org = get_organization_by_slug(ctx.tenant_key or "")
            if not org:
                return Response(
                    {"detail": "Unknown tenant."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            provision_tenant_database(org.slug, db_name=org.tenant_db_name)

        user = authenticate(
            username=data["username"], password=data["password"]
        )
        if not user:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if ctx.scope == "core":
            tokens = _issue_tokens(user=user, scope="core")
        else:
            tokens = _issue_tokens(
                user=user, scope="tenant", tenant=ctx.tenant_key
            )

        return Response({"tokens": tokens})


class OrganizationCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ctx = get_tenant_context()
        if ctx.scope != "core":
            return Response(
                {"detail": "Organizations are created in core context only."},
                status=400,
            )

        ser = OrganizationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        with transaction.atomic(using="default"):
            org: Organization = ser.save(owner=request.user, tenant_db_name="")
            # Compute tenant DB name and persist
            org.tenant_db_name = tenant_db_name(org.slug)
            org.save(update_fields=["tenant_db_name"])

        # Provision tenant DB + migrate and sync owner
        info = provision_tenant_database(org.slug, db_name=org.tenant_db_name)

        # Sync owner user record into tenant DB (copy hashed password)
        core_user = request.user
        User.objects.db_manager(info.db_alias).update_or_create(
            username=core_user.username,
            defaults={
                "email": core_user.email,
                "first_name": core_user.first_name,
                "last_name": core_user.last_name,
                "password": core_user.password,
                "is_active": core_user.is_active,
            },
        )

        return Response(
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "tenant_db_name": org.tenant_db_name,
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ctx = get_tenant_context()
        if ctx.scope != "tenant":
            return Response(
                {"detail": "Me endpoint is available only in tenant context."},
                status=400,
            )
        return Response(UserMeSerializer(request.user).data)

    def put(self, request):
        ctx = get_tenant_context()
        if ctx.scope != "tenant":
            return Response(
                {"detail": "Me endpoint is available only in tenant context."},
                status=400,
            )

        ser = UserMeSerializer(
            instance=request.user, data=request.data, partial=False
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
