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


# Endpoints for the hosted providers, used when a provider row has no explicit
# base_url. Keeping them here means "enable Hugging Face" is one row plus a
# credential, not a URL nobody remembers.
_DEFAULT_BASE_URLS: dict[str, str] = {
    'huggingface': 'https://router.huggingface.co/v1',
    'openrouter': 'https://openrouter.ai/api/v1',
    'together': 'https://api.together.xyz/v1',
    'vercel_ai_gateway': 'https://ai-gateway.vercel.sh/v1',
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
        base_url = (
            self.base_urls.get(provider_id)
            or provider_row.get('base_url')
            or _DEFAULT_BASE_URLS.get(provider_row['kind'])
        )
        return factory(
            api_key=self.credentials.get(provider_id),
            base_url=base_url,
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
