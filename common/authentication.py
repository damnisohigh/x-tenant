from __future__ import annotations

from typing import Optional, Tuple

from django.contrib.auth.models import AnonymousUser
from django.db import connections
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from common.tenant_context import get_tenant_context


class ScopedJWTAuthentication(JWTAuthentication):
    """
    JWT auth aware of current DB alias (core vs tenant) and enforces:
    - core endpoints: token.scope == "core"
    - tenant endpoints: token.scope == "tenant" AND token.tenant == X-TENANT
    """

    def authenticate(
        self, request: Request
    ) -> Optional[Tuple[object, object]]:
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        ctx = get_tenant_context()

        token_scope = validated_token.get("scope")
        token_tenant = validated_token.get("tenant")

        if ctx.scope == "core":
            if token_scope != "core":
                raise InvalidToken("Token scope mismatch (expected core).")
        else:
            if token_scope != "tenant":
                raise InvalidToken("Token scope mismatch (expected tenant).")
            if not ctx.tenant_key or token_tenant != ctx.tenant_key:
                raise InvalidToken("Token tenant mismatch.")

        # Ensure connection exists (middleware sets alias, but DB is dynamic).
        connections[ctx.db_alias]

        user = self.get_user(validated_token)
        return (user, validated_token)

    def get_user(self, validated_token):
        """
        Same as SimpleJWT but querying via the current DB alias.
        """
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.settings import api_settings

        user_id_claim = api_settings.USER_ID_CLAIM
        user_id_field = api_settings.USER_ID_FIELD

        user_id = validated_token.get(user_id_claim)
        if user_id is None:
            raise InvalidToken(
                "Token contained no recognizable user identification."
            )

        User = get_user_model()
        ctx = get_tenant_context()

        try:
            user = User.objects.db_manager(ctx.db_alias).get(
                **{user_id_field: user_id}
            )
        except User.DoesNotExist:
            return AnonymousUser()

        if not user.is_active:
            return AnonymousUser()

        return user
