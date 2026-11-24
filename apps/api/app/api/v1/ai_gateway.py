from fastapi import APIRouter, Depends, HTTPException

from app.ai_gateway.registry import ProviderRegistry
from app.api.deps import OrganizationContext, get_org_context
from app.api.errors import translate_supabase_error
from app.core.config import Settings, get_settings
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.models import ModelsRepository
from app.repositories.org_ai import OrgAIRepository
from app.repositories.usage import UsageRepository
from app.schemas.ai_gateway import GenerateIn, GenerateOut
from app.security.secrets import SecretBox, SecretBoxUnavailable
from app.services.ai_gateway import (
    AIGatewayService,
    BudgetExceeded,
    EntitlementMissing,
    ModelUnavailable,
)
from app.services.org_ai import OrgAIService

router = APIRouter(prefix='/ai', tags=['ai-gateway'])


def get_ai_gateway_service(
    client: SupabaseClient = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> AIGatewayService:
    registry = ProviderRegistry(
        credentials=settings.ai_provider_credentials,
        base_urls=settings.ai_provider_base_urls,
        timeout=settings.ai_gateway_timeout_seconds,
    )
    secret_box: SecretBox | None = None
    if settings.secret_key:
        try:
            secret_box = SecretBox(settings.secret_key)
        except SecretBoxUnavailable:
            secret_box = None
    org_ai = OrgAIService(OrgAIRepository(client), secret_box)
    return AIGatewayService(
        ModelsRepository(client),
        UsageRepository(client),
        registry,
        credits_per_1k_tokens=settings.ai_gateway_credits_per_1k_tokens,
        # Tenant keys and limits override the deployment defaults per request.
        credential_resolver=org_ai.resolve_credentials,
        settings_resolver=org_ai.settings_for_server,
    )


@router.post('/generate', response_model=GenerateOut)
async def generate(
    payload: GenerateIn,
    context: OrganizationContext = Depends(get_org_context),
    service: AIGatewayService = Depends(get_ai_gateway_service),
):
    try:
        return await service.generate(
            context.access_token, context.organization_id, context.user_id, payload
        )
    except EntitlementMissing as exc:
        raise HTTPException(status_code=404, detail='no active entitlement for this organization') from exc
    except BudgetExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc, not_found_detail='entitlement not found') from exc
