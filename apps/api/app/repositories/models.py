from __future__ import annotations

from typing import Any

from app.database.supabase import SupabaseClient

_PROVIDER_SELECT = 'id,name,kind,base_url,enabled,capabilities'
_MODEL_SELECT = (
    'id,provider_id,display_name,description,task,modalities,context_window,'
    'max_output_tokens,supports_tools,supports_streaming,supports_vision,'
    'supports_embeddings,input_cost_per_1k,output_cost_per_1k,currency,status,'
    'limits,capabilities'
)


class ModelsRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def list_providers(self, access_token: str) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'ai_providers', access_token=access_token,
            params={'select': _PROVIDER_SELECT, 'order': 'id.asc'},
        )
        return result or []

    async def list_models(self, access_token: str) -> list[dict[str, Any]]:
        result = await self.client.request(
            'GET', 'ai_models', access_token=access_token,
            params={'select': _MODEL_SELECT, 'order': 'id.asc'},
        )
        return result or []

    async def get_model(self, access_token: str, model_id: str) -> dict[str, Any] | None:
        result = await self.client.request(
            'GET', 'ai_models', access_token=access_token,
            params={'select': _MODEL_SELECT, 'id': f'eq.{model_id}', 'limit': '1'},
        )
        return result[0] if result else None

    async def create_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.client.request(
            'POST', 'ai_providers', admin=True, json=data, prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def update_provider(self, provider_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        result = await self.client.request(
            'PATCH', 'ai_providers', admin=True,
            params={'id': f'eq.{provider_id}'}, json=data, prefer='return=representation',
        )
        return result[0] if result else None

    async def create_model(self, data: dict[str, Any]) -> dict[str, Any]:
        result = await self.client.request(
            'POST', 'ai_models', admin=True, json=data, prefer='return=representation',
        )
        return result[0] if isinstance(result, list) else result

    async def update_model(self, model_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        result = await self.client.request(
            'PATCH', 'ai_models', admin=True,
            params={'id': f'eq.{model_id}'}, json=data, prefer='return=representation',
        )
        return result[0] if result else None
