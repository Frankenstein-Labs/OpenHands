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
