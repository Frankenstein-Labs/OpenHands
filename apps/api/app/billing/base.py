from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import httpx

from app.core.config import Settings


class BillingNotConfigured(RuntimeError):
    pass


@dataclass
class CheckoutSession:
    id: str
    url: str


class BillingProvider(Protocol):
    name: str

    async def create_checkout_session(
        self,
        *,
        organization_id: UUID,
        plan_id: str,
        customer_email: str | None,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession: ...


class NoopBillingProvider:
    """Default provider used when no payment credentials are configured."""

    name = 'none'

    async def create_checkout_session(self, **_: object) -> CheckoutSession:
        raise BillingNotConfigured('billing is not configured')


class StripeBillingProvider:
    name = 'stripe'

    def __init__(
        self,
        api_key: str,
        price_ids: dict[str, str],
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.price_ids = price_ids
        self.client = client or httpx.AsyncClient(timeout=20.0)

    async def create_checkout_session(
        self,
        *,
        organization_id: UUID,
        plan_id: str,
        customer_email: str | None,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        price_id = self.price_ids.get(plan_id)
        if not price_id:
            raise BillingNotConfigured(f'no Stripe price configured for plan {plan_id}')
        form = {
            'mode': 'subscription',
            'success_url': success_url,
            'cancel_url': cancel_url,
            'line_items[0][price]': price_id,
            'line_items[0][quantity]': '1',
            'client_reference_id': str(organization_id),
        }
        if customer_email:
            form['customer_email'] = customer_email
        try:
            response = await self.client.post(
                'https://api.stripe.com/v1/checkout/sessions',
                data=form,
                auth=(self.api_key, ''),
            )
        except httpx.HTTPError as exc:
            raise BillingNotConfigured('Stripe is unavailable') from exc
        if response.is_error:
            raise BillingNotConfigured(f'Stripe returned {response.status_code}')
        data = response.json()
        return CheckoutSession(id=data['id'], url=data['url'])


def get_billing_provider(settings: Settings) -> BillingProvider:
    if not settings.stripe_secret_key:
        return NoopBillingProvider()
    return StripeBillingProvider(settings.stripe_secret_key, settings.stripe_price_ids)
