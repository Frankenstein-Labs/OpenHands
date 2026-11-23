from __future__ import annotations

import httpx

from app.ai_gateway.openai_compatible import OpenAICompatibleProvider


class FrankensteinProvider(OpenAICompatibleProvider):
    """Frankenstein-Labs models (e.g. Cortex-0) served from a remote endpoint.

    The endpoint is OpenAI-compatible. It is never considered available until a
    real ``base_url`` is configured server-side, so Cortex-0 is not advertised as
    usable before deployment.
    """

    kind = 'frankenstein'

    async def health(self) -> bool:
        if not self.configured:
            return False
        client = self._get_client()
        for path in ('/health', '/models'):
            try:
                response = await client.get(f'{self.base_url}{path}', headers=self._headers())
            except httpx.HTTPError:
                continue
            if response.status_code < 400:
                return True
        return False
