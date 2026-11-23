from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from app.ai_gateway.base import Provider
from app.ai_gateway.errors import (
    GatewayError,
    NoAvailableModel,
    ProviderError,
    ProviderNotConfigured,
)
from app.ai_gateway.types import GenerationRequest, GenerationResult, ModelSpec


class ModelRouter:
    """Chooses a model by task and falls back across providers.

    Fallback only happens for idempotent requests and retryable errors. A
    non-idempotent request (e.g. tool call with side effects) is never retried
    blindly against another provider.
    """

    def __init__(self, models: Mapping[str, ModelSpec], providers: Mapping[str, Provider]) -> None:
        self.models = models
        self.providers = providers

    def _eligible(
        self,
        request: GenerationRequest,
        task: str,
        require_tools: bool,
        require_vision: bool,
    ) -> list[ModelSpec]:
        eligible: list[ModelSpec] = []
        for spec in self.models.values():
            if spec.status != 'active':
                continue
            provider = self.providers.get(spec.provider_id)
            if provider is None or not provider.configured:
                continue
            if require_tools and not spec.supports_tools:
                continue
            if require_vision and not spec.supports_vision:
                continue
            eligible.append(spec)

        def rank(spec: ModelSpec) -> tuple[int, str]:
            if spec.id == request.model:
                task_rank = -1
            elif spec.task == task:
                task_rank = 0
            elif spec.task == 'general':
                task_rank = 1
            else:
                task_rank = 2
            return (task_rank, spec.id)

        return sorted(eligible, key=rank)

    async def generate(
        self,
        request: GenerationRequest,
        *,
        task: str = 'general',
        require_tools: bool | None = None,
        require_vision: bool = False,
    ) -> GenerationResult:
        tools_required = bool(request.tools) if require_tools is None else require_tools
        candidates = self._eligible(request, task, tools_required, require_vision)
        if not candidates:
            raise NoAvailableModel('no configured model matches the request')

        last_error: GatewayError | None = None
        for spec in candidates:
            provider = self.providers[spec.provider_id]
            try:
                return await provider.generate(replace(request, model=spec.id))
            except ProviderNotConfigured as exc:
                last_error = exc
                continue
            except ProviderError as exc:
                last_error = exc
                if not request.idempotent or not exc.retryable:
                    raise
                continue
        raise last_error or NoAvailableModel('no configured model matches the request')
