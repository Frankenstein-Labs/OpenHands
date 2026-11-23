from __future__ import annotations

from typing import Any

from app.repositories.models import ModelsRepository

# A model is usable only when its provider is enabled AND the model is fully active.
# "preview" models (e.g. Cortex-0 without an endpoint) are listed but never "available".
_AVAILABLE_MODEL_STATUSES = {'active'}


class ModelsService:
    def __init__(self, repository: ModelsRepository) -> None:
        self.repository = repository

    async def list_providers(self, access_token: str, *, only_enabled: bool = False) -> list[dict[str, Any]]:
        providers = await self.repository.list_providers(access_token)
        if only_enabled:
            return [p for p in providers if p.get('enabled')]
        return providers

    async def _decorate(self, access_token: str) -> list[dict[str, Any]]:
        providers = {p['id']: p for p in await self.repository.list_providers(access_token)}
        models = await self.repository.list_models(access_token)
        decorated = []
        for model in models:
            provider = providers.get(model['provider_id'], {})
            provider_enabled = bool(provider.get('enabled'))
            available = provider_enabled and model.get('status') in _AVAILABLE_MODEL_STATUSES
            decorated.append({**model, 'provider_enabled': provider_enabled, 'available': available})
        return decorated

    async def list_models(self, access_token: str) -> list[dict[str, Any]]:
        return await self._decorate(access_token)

    async def list_available(self, access_token: str) -> list[dict[str, Any]]:
        return [m for m in await self._decorate(access_token) if m['available']]

    async def is_available(self, access_token: str, model_id: str) -> bool:
        model = await self.repository.get_model(access_token, model_id)
        if model is None:
            return False
        providers = {p['id']: p for p in await self.repository.list_providers(access_token)}
        return bool(providers.get(model['provider_id'], {}).get('enabled')) and model.get('status') in _AVAILABLE_MODEL_STATUSES

    async def create_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self.repository.create_provider(data)

    async def update_provider(self, provider_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        return await self.repository.update_provider(provider_id, data)

    async def create_model(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self.repository.create_model(data)

    async def update_model(self, model_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        return await self.repository.update_model(model_id, data)
