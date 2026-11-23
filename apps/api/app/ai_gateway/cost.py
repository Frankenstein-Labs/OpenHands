from __future__ import annotations

from decimal import Decimal

from app.ai_gateway.types import ModelSpec, Usage


def estimate_cost(usage: Usage, spec: ModelSpec) -> Decimal:
    """Estimate cost in the model's currency.

    Returns ``Decimal('0')`` when the model has no declared pricing, rather than
    inventing a price.
    """
    if spec.input_cost_per_1k is None and spec.output_cost_per_1k is None:
        return Decimal('0')
    thousand = Decimal(1000)
    input_cost = Decimal(str(spec.input_cost_per_1k or 0)) * Decimal(usage.input_tokens) / thousand
    output_cost = Decimal(str(spec.output_cost_per_1k or 0)) * Decimal(usage.output_tokens) / thousand
    return (input_cost + output_cost).quantize(Decimal('0.000001'))
