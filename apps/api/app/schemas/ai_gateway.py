from typing import Literal

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    role: Literal['system', 'user', 'assistant', 'tool']
    content: str = Field(min_length=1, max_length=200000)


class GenerateIn(BaseModel):
    model_id: str = Field(min_length=1, max_length=128)
    messages: list[MessageIn] = Field(min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=100000)
    task: Literal['general', 'coding', 'reasoning', 'light', 'vision'] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class GenerateOut(BaseModel):
    model: str
    content: str
    finish_reason: str | None = None
    usage: UsageOut
    credits_charged: float
