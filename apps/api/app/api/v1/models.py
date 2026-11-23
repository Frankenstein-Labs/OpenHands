from fastapi import APIRouter, Depends, HTTPException

from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.models import ModelsRepository
from app.schemas.models import ModelResponse, ProviderResponse
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.models import ModelsService

router = APIRouter(tags=['ai-catalog'])


def get_models_service(client: SupabaseClient = Depends(get_supabase_client)) -> ModelsService:
    return ModelsService(ModelsRepository(client))


def _raise(exc: Exception) -> None:
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc) from exc
    raise exc


@router.get('/providers', response_model=list[ProviderResponse])
async def list_providers(
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.list_providers(access_token)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/models', response_model=list[ModelResponse])
async def list_models(
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.list_models(access_token)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/models/available', response_model=list[ModelResponse])
async def list_available_models(
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.list_available(access_token)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
