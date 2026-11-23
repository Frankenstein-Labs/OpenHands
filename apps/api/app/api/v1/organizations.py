from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.schemas.organizations import OrganizationCreate, OrganizationResponse, OrganizationUpdate
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.organizations import OrganizationNotFound, OrganizationsService

router = APIRouter(prefix='/organizations', tags=['organizations'])


def get_organizations_service(client: SupabaseClient = Depends(get_supabase_client)) -> OrganizationsService:
    return OrganizationsService(client)


def translate_supabase_error(exc: SupabaseRequestError) -> HTTPException:
    if exc.status_code in (401, 403, 404):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Resource not found')
    if exc.status_code == 409:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Organization already exists')
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Supabase request failed')


@router.get('', response_model=list[OrganizationResponse])
async def list_organizations(
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: OrganizationsService = Depends(get_organizations_service),
):
    try:
        return await service.list_organizations(access_token)
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc


@router.post('', response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: OrganizationsService = Depends(get_organizations_service),
):
    try:
        return await service.create_organization(access_token, payload)
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc


@router.get('/{organization_id}', response_model=OrganizationResponse)
async def get_organization(
    organization_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: OrganizationsService = Depends(get_organizations_service),
):
    try:
        return await service.get_organization(access_token, organization_id)
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail='Organization not found') from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc


@router.patch('/{organization_id}', response_model=OrganizationResponse)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: OrganizationsService = Depends(get_organizations_service),
):
    try:
        return await service.update_organization(access_token, organization_id, payload)
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail='Organization not found') from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc
