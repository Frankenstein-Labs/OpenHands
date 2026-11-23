from typing import Any, Literal

from pydantic import BaseModel, Field


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


ProviderKind = Literal[
    'openai_compatible',
    'vercel_ai_gateway',
    'huggingface',
    'openrouter',
    'together',
    'cloudflare_workers_ai',
    'frankenstein',
]
ModelTask = Literal['general', 'coding', 'reasoning', 'light', 'vision', 'embedding']
ModelStatus = Literal['active', 'preview', 'disabled', 'retired']


class ProviderCreate(BaseModel):
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{1,63}$')
    name: str = Field(min_length=1, max_length=200)
    kind: ProviderKind
    base_url: str | None = Field(default=None, max_length=2000)
    enabled: bool = False
    capabilities: dict[str, Any] = {}


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
    capabilities: dict[str, Any] | None = None


class ModelCreate(BaseModel):
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9._:/-]{1,127}$')
    provider_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    task: ModelTask = 'general'
    modalities: list[str] = ['text']
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    supports_tools: bool = False
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_embeddings: bool = False
    input_cost_per_1k: float | None = Field(default=None, ge=0)
    output_cost_per_1k: float | None = Field(default=None, ge=0)
    currency: str = Field(default='USD', min_length=3, max_length=8)
    status: ModelStatus = 'preview'
    limits: dict[str, Any] = {}
    capabilities: dict[str, Any] = {}


class ModelUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    task: ModelTask | None = None
    modalities: list[str] | None = None
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    supports_tools: bool | None = None
    supports_streaming: bool | None = None
    supports_vision: bool | None = None
    supports_embeddings: bool | None = None
    input_cost_per_1k: float | None = Field(default=None, ge=0)
    output_cost_per_1k: float | None = Field(default=None, ge=0)
    status: ModelStatus | None = None
    limits: dict[str, Any] | None = None
    capabilities: dict[str, Any] | None = None
