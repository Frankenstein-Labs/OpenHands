from uuid import uuid4

import httpx
import pytest

from app.billing.base import BillingNotConfigured, NoopBillingProvider, StripeBillingProvider
from app.schemas.billing import CheckoutRequest
from app.services.billing import BillingService


class FakeBillingRepository:
    async def list_plans(self, access_token):
        return []

    async def get_subscription(self, access_token, organization_id):
        return None

    async def list_invoices(self, access_token, organization_id):
        return []


@pytest.mark.asyncio
async def test_noop_provider_refuses_checkout() -> None:
    service = BillingService(
        FakeBillingRepository(), NoopBillingProvider(), success_url='s', cancel_url='c'
    )
    with pytest.raises(BillingNotConfigured):
        await service.checkout('t', uuid4(), CheckoutRequest(plan_id='pro'))


@pytest.mark.asyncio
async def test_stripe_provider_creates_checkout_session() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/v1/checkout/sessions'
        assert 'price_pro' in request.content.decode()
        return httpx.Response(200, json={'id': 'cs_1', 'url': 'https://pay.example'})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = StripeBillingProvider('sk_test', {'pro': 'price_pro'}, client=client)
    session = await provider.create_checkout_session(
        organization_id=uuid4(),
        plan_id='pro',
        customer_email=None,
        success_url='s',
        cancel_url='c',
    )
    await client.aclose()
    assert session.url == 'https://pay.example'


@pytest.mark.asyncio
async def test_subscription_defaults_when_absent() -> None:
    service = BillingService(
        FakeBillingRepository(), NoopBillingProvider(), success_url=None, cancel_url=None
    )
    org = uuid4()
    result = await service.subscription('t', org)
    assert result['organization_id'] == org
    assert result['plan_id'] is None
