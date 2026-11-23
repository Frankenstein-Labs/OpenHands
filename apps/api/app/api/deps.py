from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.memberships import MembershipsRepository
from app.security.jwt import CurrentUser, get_access_token, get_current_user


@dataclass(frozen=True)
class OrganizationContext:
    organization_id: UUID
    user_id: str
    role: str
    access_token: str


async def _resolve_context(
    client: SupabaseClient,
    access_token: str,
    user: CurrentUser,
    organization_id: UUID,
) -> OrganizationContext:
    """Resolve the caller's membership server-side.

    The browser-supplied organization id is only used to look up a membership; it
    never grants access on its own. A non-member gets 404 so tenant existence is
    not leaked.
    """
    try:
        membership = await MembershipsRepository(client).get_actor_membership(
            access_token, organization_id, user.id
        )
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise HTTPException(status_code=502, detail='Supabase request failed') from exc
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Organization not found')
    return OrganizationContext(
        organization_id=organization_id,
        user_id=user.id,
        role=membership['role'],
        access_token=access_token,
    )


async def get_org_context(
    organization_id: UUID = Query(..., description='Active organization id'),
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    client: SupabaseClient = Depends(get_supabase_client),
) -> OrganizationContext:
    return await _resolve_context(client, access_token, user, organization_id)


async def get_path_org_context(
    organization_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    client: SupabaseClient = Depends(get_supabase_client),
) -> OrganizationContext:
    return await _resolve_context(client, access_token, user, organization_id)


def require_platform_admin(user: CurrentUser, settings: Settings = Depends(get_settings)) -> None:
    if not settings.platform_admin_user_ids or user.id not in settings.platform_admin_user_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Platform administrator access required',
        )


def require_role(context: OrganizationContext, allowed: set[str]) -> None:
    if context.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Insufficient organization permissions',
        )
