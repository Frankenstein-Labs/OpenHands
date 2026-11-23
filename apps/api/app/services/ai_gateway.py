from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.ai_gateway.errors import GatewayError
from app.ai_gateway.registry import ProviderRegistry
from app.ai_gateway.router import ModelRouter
from app.ai_gateway.types import GenerationRequest, Message, ModelSpec
from app.repositories.models import ModelsRepository
from app.repositories.usage import UsageRepository


class BudgetExceeded(Exception):
    pass


class EntitlementMissing(Exception):
    pass


class ModelUnavailable(Exception):
    pass


def _month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def spec_from_row(row: dict[str, Any]) -> ModelSpec:
    return ModelSpec(
        id=row['id'],
        provider_id=row['provider_id'],
        task=row.get('task') or 'general',
        modalities=tuple(row.get('modalities') or ('text',)),
        context_window=row.get('context_window'),
        supports_tools=bool(row.get('supports_tools')),
        supports_streaming=bool(row.get('supports_streaming', True)),
        supports_vision=bool(row.get('supports_vision')),
        supports_embeddings=bool(row.get('supports_embeddings')),
        input_cost_per_1k=row.get('input_cost_per_1k'),
        output_cost_per_1k=row.get('output_cost_per_1k'),
        currency=row.get('currency') or 'USD',
        status=row.get('status') or 'active',
    )


def build_router(
    model_rows: list[dict[str, Any]],
    provider_rows: list[dict[str, Any]],
    registry: ProviderRegistry,
    credentials: dict[str, str] | None = None,
) -> ModelRouter:
    providers = (
        registry.build_enabled(provider_rows)
        if credentials is None
        else registry.build_enabled(provider_rows, credentials)
    )
    specs = {
        row['id']: spec_from_row(row)
        for row in model_rows
        if row['provider_id'] in providers and (row.get('status') or 'active') == 'active'
    }
    return ModelRouter(specs, providers)


class AIGatewayService:
    def __init__(
        self,
        models: ModelsRepository,
        usage: UsageRepository,
        registry: ProviderRegistry,
        *,
        credits_per_1k_tokens: float = 1.0,
        credential_resolver: Any = None,
        settings_resolver: Any = None,
    ) -> None:
        self.models = models
        self.usage = usage
        self.registry = registry
        self.credits_per_1k_tokens = credits_per_1k_tokens
        # Async callables taking an organization id. When present, the
        # organization's own provider keys, rate and token ceiling take
        # precedence over the deployment defaults.
        self.credential_resolver = credential_resolver
        self.settings_resolver = settings_resolver

    async def generate(
        self,
        access_token: str,
        organization_id: UUID,
        user_id: str,
        request: Any,
    ) -> dict[str, Any]:
        entitlement = await self.usage.get_entitlement(access_token, organization_id)
        if entitlement is None:
            raise EntitlementMissing
        remaining = float(entitlement['credits_limit']) - float(entitlement['credits_used'])
        if remaining <= 0:
            raise BudgetExceeded('organization credit limit reached')
        org_settings = (
            await self.settings_resolver(organization_id)
            if self.settings_resolver is not None
            else None
        ) or {}
        rate = org_settings.get('credits_per_1k_tokens')
        credits_per_1k = float(rate) if rate is not None else self.credits_per_1k_tokens

        if request.max_tokens is not None:
            allowed_tokens = int(remaining / credits_per_1k * 1000)
            if request.max_tokens > allowed_tokens:
                raise BudgetExceeded('requested max_tokens exceeds remaining credits')

        token_limit = org_settings.get('monthly_token_limit')
        if token_limit is not None:
            used = await self.usage.tokens_since(
                organization_id, _month_start_iso()
            )
            if used + (request.max_tokens or 0) > int(token_limit):
                raise BudgetExceeded('organization monthly token limit reached')

        credentials = None
        if self.credential_resolver is not None:
            tenant_credentials = dict(await self.credential_resolver(organization_id))
            if tenant_credentials:
                # Tenant keys win over deployment defaults, and are passed per
                # request so they never leak into a shared registry.
                credentials = {**self.registry.credentials, **tenant_credentials}

        router = build_router(
            await self.models.list_models(access_token),
            await self.models.list_providers(access_token),
            self.registry,
            credentials,
        )
        if request.model_id not in router.models:
            raise ModelUnavailable('model is unknown, inactive, or its provider is not configured')

        try:
            result = await router.generate(
                GenerationRequest(
                    model=request.model_id,
                    messages=[Message(role=message.role, content=message.content) for message in request.messages],
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ),
                task=request.task or 'general',
                require_vision=request.task == 'vision',
            )
        except GatewayError as exc:
            raise ModelUnavailable(str(exc)) from exc

        credits = round(result.usage.total_tokens / 1000 * credits_per_1k, 6)
        await self.usage.record_event(
            organization_id=organization_id,
            actor_user_id=user_id,
            event_type='llm_tokens',
            quantity=result.usage.total_tokens,
            credits=credits,
            idempotency_key=request.idempotency_key or uuid.uuid4().hex,
            metadata={
                'model': result.model,
                'input_tokens': result.usage.input_tokens,
                'output_tokens': result.usage.output_tokens,
            },
        )
        return {
            'model': result.model,
            'content': result.content,
            'finish_reason': result.finish_reason,
            'usage': {
                'input_tokens': result.usage.input_tokens,
                'output_tokens': result.usage.output_tokens,
                'total_tokens': result.usage.total_tokens,
            },
            'credits_charged': credits,
        }
