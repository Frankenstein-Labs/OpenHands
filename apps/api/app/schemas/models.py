from typing import Any

from pydantic import BaseModel


class ProviderResponse(BaseModel):
    id: str
    name: str
    kind: str
    base_url: str | None = None
    enabled: bool
    capabilities: dict[str, Any] = {}


class ModelResponse(BaseModel):
    id: str
    provider_id: str
    display_name: str
    description: str | None = None
    task: str
    modalities: list[str] = []
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_tools: bool
    supports_streaming: bool
    supports_vision: bool
    supports_embeddings: bool
    input_cost_per_1k: float | None = None
    output_cost_per_1k: float | None = None
    currency: str
    status: str
    limits: dict[str, Any] = {}
    capabilities: dict[str, Any] = {}
    provider_enabled: bool = False
    available: bool = False
