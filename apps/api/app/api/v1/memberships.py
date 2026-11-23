from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.memberships import MembershipsRepository
from app.schemas.memberships import (
    AddMemberRequest,
    MembershipResponse,
    TransferOwnershipRequest,
    UpdateMemberRoleRequest,
)
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.memberships import MembershipAccessDenied, MembershipNotFound, MembershipsService

router = APIRouter(prefix='/organizations/{organization_id}/members', tags=['memberships'])


def get_memberships_service(client: SupabaseClient = Depends(get_supabase_client)) -> MembershipsService:
    return MembershipsService(MembershipsRepository(client))


def translate_membership_error(exc: SupabaseRequestError) -> HTTPException:
    if exc.status_code in (401, 403):
        return HTTPException(status_code=403, detail='Membership operation is not permitted')
    if exc.status_code == 409:
        return HTTPException(status_code=409, detail='Membership already exists')
    if exc.status_code == 404:
        return HTTPException(status_code=404, detail='Membership not found')
    return HTTPException(status_code=502, detail='Supabase request failed')


def translate_access_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MembershipNotFound):
        return HTTPException(status_code=404, detail='Organization or membership not found')
    if isinstance(exc, MembershipAccessDenied):
        return HTTPException(status_code=403, detail='Insufficient organization permissions')
    raise exc


@router.get('', response_model=list[MembershipResponse])
async def list_members(
    organization_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: MembershipsService = Depends(get_memberships_service),
):
    try:
        return await service.list_members(access_token, user.id, organization_id)
    except (MembershipNotFound, MembershipAccessDenied) as exc:
        raise translate_access_error(exc) from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_membership_error(exc) from exc


@router.post('', response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    organization_id: UUID,
    payload: AddMemberRequest,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: MembershipsService = Depends(get_memberships_service),
):
    try:
        return await service.add_member(access_token, user.id, organization_id, payload.user_id, payload.role)
    except (MembershipNotFound, MembershipAccessDenied) as exc:
        raise translate_access_error(exc) from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_membership_error(exc) from exc


@router.post('/transfer-ownership', response_model=MembershipResponse)
async def transfer_ownership(
    organization_id: UUID,
    payload: TransferOwnershipRequest,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: MembershipsService = Depends(get_memberships_service),
):
    try:
        return await service.transfer_ownership(access_token, user.id, organization_id, payload.new_owner_user_id)
    except (MembershipNotFound, MembershipAccessDenied) as exc:
        raise translate_access_error(exc) from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_membership_error(exc) from exc


@router.patch('/{member_user_id}', response_model=MembershipResponse)
async def update_member_role(
    organization_id: UUID,
    member_user_id: UUID,
    payload: UpdateMemberRoleRequest,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: MembershipsService = Depends(get_memberships_service),
):
    try:
        return await service.update_role(access_token, user.id, organization_id, member_user_id, payload.role)
    except (MembershipNotFound, MembershipAccessDenied) as exc:
        raise translate_access_error(exc) from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_membership_error(exc) from exc


@router.delete('/{member_user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    organization_id: UUID,
    member_user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: MembershipsService = Depends(get_memberships_service),
):
    try:
        await service.remove_member(access_token, user.id, organization_id, member_user_id)
    except (MembershipNotFound, MembershipAccessDenied) as exc:
        raise translate_access_error(exc) from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_membership_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
