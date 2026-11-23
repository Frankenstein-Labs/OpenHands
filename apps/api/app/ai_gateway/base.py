from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from app.ai_gateway.errors import CapabilityNotSupported, ProviderNotConfigured
from app.ai_gateway.types import GenerationRequest, GenerationResult


class Provider(ABC):
    """Common provider interface.

    Capabilities are opt-in: a provider that cannot stream or embed inherits the
    default methods that raise ``CapabilityNotSupported``. Callers must never
    assume every provider supports everything.
    """

    kind: str = 'base'

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/') if base_url else None
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None
        self.extra_headers = extra_headers or {}

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _get_client(self) -> httpx.AsyncClient:
        if not self.configured:
            raise ProviderNotConfigured(f'{self.kind} provider has no configured endpoint')
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            self._owns_client = True
        return self._client

    def _headers(self) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        headers.update(self.extra_headers)
        return headers

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Return a single completion."""

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        raise CapabilityNotSupported(f'{self.kind} does not support streaming')
        yield ''  # pragma: no cover - marks this as an async generator

    async def embeddings(self, model: str, inputs: list[str]) -> list[list[float]]:
        raise CapabilityNotSupported(f'{self.kind} does not support embeddings')

    async def health(self) -> bool:
        return False
