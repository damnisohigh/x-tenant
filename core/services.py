from __future__ import annotations

from typing import Optional

from core.models import Organization


def get_organization_by_slug(slug: str) -> Optional[Organization]:
    return Organization.objects.using("default").filter(slug=slug).first()
