from fastapi import APIRouter, Depends, HTTPException

from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.profiles import ProfilesRepository
from app.schemas.profiles import ProfileResponse, ProfileUpdate
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.profiles import ProfilesService

router = APIRouter(prefix='/profile', tags=['profiles'])


def get_profiles_service(client: SupabaseClient = Depends(get_supabase_client)) -> ProfilesService:
    return ProfilesService(ProfilesRepository(client))


@router.get('', response_model=ProfileResponse)
async def get_profile(
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ProfilesService = Depends(get_profiles_service),
):
    try:
        return await service.get_or_create(access_token, user.id)
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc


@router.patch('', response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ProfilesService = Depends(get_profiles_service),
):
    try:
        return await service.update(access_token, user.id, payload)
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc
