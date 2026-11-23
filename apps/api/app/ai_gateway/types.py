from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass
class GenerationRequest:
    model: str
    messages: list[Message]
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict] | None = None
    stream: bool = False
    # When False (e.g. a call with side effects via tools), the router must not
    # fall back to another provider after a partial/failed attempt.
    idempotent: bool = True


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class GenerationResult:
    model: str
    content: str
    finish_reason: str | None = None
    usage: Usage = field(default_factory=Usage)
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSpec:
    """Declared capabilities of a model in the Cortex catalogue."""

    id: str
    provider_id: str
    task: str = 'general'
    modalities: tuple[str, ...] = ('text',)
    context_window: int | None = None
    supports_tools: bool = False
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_embeddings: bool = False
    input_cost_per_1k: float | None = None
    output_cost_per_1k: float | None = None
    currency: str = 'USD'
    status: str = 'active'
