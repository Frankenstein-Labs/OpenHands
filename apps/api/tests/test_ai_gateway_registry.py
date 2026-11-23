import httpx


def test_registry_applies_provider_default_endpoint_and_credential():
    from app.ai_gateway.registry import ProviderRegistry

    registry = ProviderRegistry(
        credentials={'hf': 'hf_test'},
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
    )

    provider = registry.build({'id': 'hf', 'kind': 'huggingface', 'enabled': True})

    assert provider is not None
    assert provider.base_url == 'https://router.huggingface.co/v1'
    assert provider.api_key == 'hf_test'


def test_registry_prefers_explicit_base_url_over_default():
    from app.ai_gateway.registry import ProviderRegistry

    registry = ProviderRegistry(base_urls={'hf': 'https://self-hosted.test/v1'})

    provider = registry.build(
        {'id': 'hf', 'kind': 'huggingface', 'enabled': True, 'base_url': 'https://row.test/v1'}
    )

    assert provider.base_url == 'https://self-hosted.test/v1'
