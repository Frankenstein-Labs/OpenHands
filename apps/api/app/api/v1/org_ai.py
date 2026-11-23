from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import OrganizationContext, get_org_context
from app.api.errors import translate_supabase_error
from app.core.config import Settings, get_settings
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.org_ai import OrgAIRepository
from app.schemas.org_ai import (
    CredentialIn,
    CredentialMetadataOut,
    CredentialOut,
    OrgAISettingsIn,
    OrgAISettingsOut,
)
from app.security.secrets import SecretBox, SecretBoxUnavailable
from app.services.org_ai import InvalidCredential, OrgAIService

router = APIRouter(tags=['org-ai'])


def get_org_ai_service(
    client: SupabaseClient = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> OrgAIService:
    secret_box: SecretBox | None = None
    if settings.secret_key:
        try:
            secret_box = SecretBox(settings.secret_key)
        except SecretBoxUnavailable:
            secret_box = None
    return OrgAIService(OrgAIRepository(client), secret_box)


def _translate(exc: Exception) -> None:
    if isinstance(exc, InvalidCredential):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc) from exc
    raise exc


@router.get('/organizations/ai-credentials', response_model=list[CredentialMetadataOut])
async def list_ai_credentials(
    context: OrganizationContext = Depends(get_org_context),
    service: OrgAIService = Depends(get_org_ai_service),
):
    """Key metadata only: the stored keys themselves are never returned."""
    try:
        return await service.list_credentials(context.access_token, context.organization_id)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _translate(exc)


@router.put(
    '/organizations/ai-credentials/{provider_id}', response_model=CredentialOut
)
async def set_ai_credential(
    provider_id: str,
    payload: CredentialIn,
    context: OrganizationContext = Depends(get_org_context),
    service: OrgAIService = Depends(get_org_ai_service),
):
    try:
        return await service.set_credential(
            context.access_token, context.organization_id, provider_id, payload.api_key
        )
    except (InvalidCredential, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _translate(exc)


@router.delete('/organizations/ai-credentials/{provider_id}')
async def revoke_ai_credential(
    provider_id: str,
    context: OrganizationContext = Depends(get_org_context),
    service: OrgAIService = Depends(get_org_ai_service),
):
    try:
        revoked = await service.revoke_credential(
            context.access_token, context.organization_id, provider_id
        )
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _translate(exc)
    if not revoked:
        raise HTTPException(status_code=404, detail='Credential not found')
    return {'revoked': True}


@router.get('/organizations/ai-settings', response_model=OrgAISettingsOut)
async def get_ai_settings(
    context: OrganizationContext = Depends(get_org_context),
    service: OrgAIService = Depends(get_org_ai_service),
):
    try:
        return await service.get_settings(context.access_token, context.organization_id)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _translate(exc)


@router.put('/organizations/ai-settings', response_model=OrgAISettingsOut)
async def update_ai_settings(
    payload: OrgAISettingsIn,
    context: OrganizationContext = Depends(get_org_context),
    service: OrgAIService = Depends(get_org_ai_service),
):
    try:
        return await service.update_settings(
            context.access_token,
            context.organization_id,
            default_model_id=payload.default_model_id,
            monthly_token_limit=payload.monthly_token_limit,
            credits_per_1k_tokens=payload.credits_per_1k_tokens,
        )
    except (InvalidCredential, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _translate(exc)
