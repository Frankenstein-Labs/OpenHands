from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.ai_gateway.base import Provider
from app.ai_gateway.errors import ProviderError, ProviderTimeout
from app.ai_gateway.types import GenerationRequest, GenerationResult, Usage

_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class OpenAICompatibleProvider(Provider):
    """Provider for any OpenAI-compatible Chat Completions API.

    Covers OpenRouter, Together, Hugging Face Inference Providers, Vercel AI
    Gateway (OpenAI mode) and self-hosted llama.cpp / vLLM servers.
    """

    kind = 'openai_compatible'

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        raise ProviderError(
            f'provider returned {response.status_code}',
            status_code=response.status_code,
            retryable=response.status_code in _RETRYABLE_STATUS,
            detail=response.text[:500],
        )

    def _payload(self, request: GenerationRequest, *, stream: bool) -> dict:
        payload: dict = {
            'model': request.model,
            'messages': [{'role': m.role, 'content': m.content} for m in request.messages],
        }
        if request.temperature is not None:
            payload['temperature'] = request.temperature
        if request.max_tokens is not None:
            payload['max_tokens'] = request.max_tokens
        if request.tools:
            payload['tools'] = request.tools
        if stream:
            payload['stream'] = True
        return payload

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        client = self._get_client()
        try:
            response = await client.post(
                f'{self.base_url}/chat/completions',
                headers=self._headers(),
                json=self._payload(request, stream=False),
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout() from exc
        except httpx.HTTPError as exc:
            raise ProviderError('provider request failed', retryable=True) from exc
        self._raise_for_status(response)
        data = response.json()
        try:
            choice = data['choices'][0]
            content = choice['message'].get('content') or ''
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError('malformed provider response') from exc
        usage = data.get('usage') or {}
        return GenerationResult(
            model=data.get('model', request.model),
            content=content,
            finish_reason=choice.get('finish_reason'),
            usage=Usage(
                input_tokens=int(usage.get('prompt_tokens') or 0),
                output_tokens=int(usage.get('completion_tokens') or 0),
            ),
            raw=data,
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        client = self._get_client()
        try:
            async with client.stream(
                'POST',
                f'{self.base_url}/chat/completions',
                headers=self._headers(),
                json=self._payload(request, stream=True),
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    self._raise_for_status(response)
                async for line in response.aiter_lines():
                    if not line.startswith('data:'):
                        continue
                    chunk = line[5:].strip()
                    if not chunk:
                        continue
                    try:
                        event = json.loads(chunk)
                    except ValueError:
                        continue
                    delta = ((event.get('choices') or [{}])[0].get('delta') or {}).get('content')
                    if delta:
                        yield delta
        except httpx.TimeoutException as exc:
            raise ProviderTimeout() from exc
        except httpx.HTTPError as exc:
            raise ProviderError('provider stream failed', retryable=True) from exc


    async def embeddings(self, model: str, inputs: list[str]) -> list[list[float]]:
        client = self._get_client()
        try:
            response = await client.post(
                f'{self.base_url}/embeddings',
                headers=self._headers(),
                json={'model': model, 'input': inputs},
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout() from exc
        except httpx.HTTPError as exc:
            raise ProviderError('provider embeddings failed', retryable=True) from exc
        self._raise_for_status(response)
        data = response.json()
        return [item['embedding'] for item in data.get('data', [])]

    async def health(self) -> bool:
        if not self.configured:
            return False
        client = self._get_client()
        try:
            response = await client.get(f'{self.base_url}/models', headers=self._headers())
        except httpx.HTTPError:
            return False
        return response.status_code < 500





