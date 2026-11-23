from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import httpx

from app.ai_gateway.base import Provider
from app.ai_gateway.frankenstein import FrankensteinProvider
from app.ai_gateway.openai_compatible import OpenAICompatibleProvider

# Kinds served through the OpenAI-compatible protocol. cloudflare_workers_ai is
# intentionally absent: it has a different protocol and is not implemented yet,
# so it is skipped instead of being mis-called.
_FACTORIES: dict[str, type[Provider]] = {
    'openai_compatible': OpenAICompatibleProvider,
    'openrouter': OpenAICompatibleProvider,
    'together': OpenAICompatibleProvider,
    'huggingface': OpenAICompatibleProvider,
    'vercel_ai_gateway': OpenAICompatibleProvider,
    'frankenstein': FrankensteinProvider,
}


class ProviderRegistry:
    def __init__(
        self,
        *,
        credentials: Mapping[str, str] | None = None,
        base_urls: Mapping[str, str] | None = None,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.credentials = dict(credentials or {})
        self.base_urls = dict(base_urls or {})
        self.timeout = timeout
        self.client = client

    def build(self, provider_row: Mapping[str, Any]) -> Provider | None:
        factory = _FACTORIES.get(provider_row['kind'])
        if factory is None:
            return None
        provider_id = provider_row['id']
        return factory(
            api_key=self.credentials.get(provider_id),
            base_url=self.base_urls.get(provider_id) or provider_row.get('base_url'),
            timeout=self.timeout,
            client=self.client,
        )

    def build_enabled(self, providers: Iterable[Mapping[str, Any]]) -> dict[str, Provider]:
        built: dict[str, Provider] = {}
        for row in providers:
            if not row.get('enabled'):
                continue
            provider = self.build(row)
            if provider is not None:
                built[row['id']] = provider
        return built
