from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import OrganizationContext, get_path_org_context, require_role
from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.invitations import InvitationsRepository
from app.schemas.invitations import (
    AcceptedMembershipResponse,
    AcceptInvitationRequest,
    InvitationCreate,
    InvitationCreatedResponse,
    InvitationResponse,
)
from app.security.jwt import get_access_token
from app.services.invitations import InvitationError, InvitationsService

router = APIRouter(tags=['invitations'])

_ADMIN_ROLES = {'owner', 'admin'}


def get_invitations_service(client: SupabaseClient = Depends(get_supabase_client)) -> InvitationsService:
    return InvitationsService(InvitationsRepository(client))


def _raise(exc: Exception) -> None:
    if isinstance(exc, InvitationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc, not_found_detail='Invitation not found') from exc
    raise exc


@router.get('/organizations/{organization_id}/invitations', response_model=list[InvitationResponse])
async def list_invitations(
    context: OrganizationContext = Depends(get_path_org_context),
    service: InvitationsService = Depends(get_invitations_service),
):
    require_role(context, _ADMIN_ROLES)
    try:
        return await service.list(context.access_token, context.organization_id)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.post(
    '/organizations/{organization_id}/invitations',
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    payload: InvitationCreate,
    context: OrganizationContext = Depends(get_path_org_context),
    service: InvitationsService = Depends(get_invitations_service),
):
    require_role(context, _ADMIN_ROLES)
    try:
        return await service.create(
            context.access_token, context.organization_id, context.user_id, payload
        )
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.post('/invitations/accept', response_model=AcceptedMembershipResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    access_token: str = Depends(get_access_token),
    service: InvitationsService = Depends(get_invitations_service),
):
    try:
        return await service.accept(access_token, payload.token)
    except (InvitationError, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
