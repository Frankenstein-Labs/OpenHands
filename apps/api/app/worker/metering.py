from __future__ import annotations

from typing import Any


def accumulated_usage(state: dict[str, Any]) -> dict[str, int]:
    """Sum the token counters of every model profile in a conversation state.

    The Agent Server keeps one metrics entry per LLM profile (the main agent and
    the condenser), each with its own `accumulated_token_usage`. Every entry is a
    real call the tenant paid for, so they are added together.
    """
    metrics = (state.get('stats') or {}).get('usage_to_metrics') or {}
    prompt_tokens = 0
    completion_tokens = 0
    for entry in metrics.values():
        usage = (entry or {}).get('accumulated_token_usage') or {}
        prompt_tokens += int(usage.get('prompt_tokens') or 0)
        completion_tokens += int(usage.get('completion_tokens') or 0)
    return {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens}


def credits_for_usage(
    usage: dict[str, int],
    model: dict[str, Any] | None,
    budget_credits: float | None = None,
) -> float:
    """Price a token count with the catalogue rates of the run's model.

    Returns 0.0 when the model has no published price, so an unpriced model never
    invents a charge. The result is clamped to the reserved budget: a run may not
    book more than it reserved, otherwise one expensive run could push the
    organization past its credit limit without any admission check.
    """
    if not model:
        return 0.0
    input_rate = float(model.get('input_cost_per_1k') or 0)
    output_rate = float(model.get('output_cost_per_1k') or 0)
    credits = (usage.get('prompt_tokens', 0) / 1000) * input_rate
    credits += (usage.get('completion_tokens', 0) / 1000) * output_rate
    credits = round(credits, 6)
    if budget_credits is not None and budget_credits > 0:
        credits = min(credits, float(budget_credits))
    return credits
