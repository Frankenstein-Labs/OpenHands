#!/usr/bin/env python3
"""Probe an AI provider before enabling it in the Cortex catalogue.

Two modes:

  endpoint  An OpenAI-compatible base URL (llama.cpp server, vLLM, Hugging Face
            Inference Endpoint, OpenRouter, Together, Vercel AI Gateway...).
  hf        A Hugging Face token/repo pair. Checks that the token is valid, that
            the model repository is reachable, and whether the model is served
            by the Hugging Face router as a chat model.

Nothing is written to disk, and secrets are never printed.

Environment (endpoint mode):
  CORTEX_VERIFY_PROVIDER_URL   e.g. https://abc.endpoints.huggingface.cloud/v1
  CORTEX_VERIFY_PROVIDER_KEY   bearer token for that endpoint
  CORTEX_VERIFY_MODEL          model id the endpoint expects

Environment (hf mode):
  CORTEX_VERIFY_HF_TOKEN       Hugging Face token
  CORTEX_VERIFY_HF_MODEL       default Frankenstein-Labs/Cortex.0

Exit codes: 0 healthy, 1 configuration error, 2 provider failure.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

HF_API = 'https://huggingface.co/api'
HF_ROUTER = 'https://router.huggingface.co/v1/chat/completions'


def _request(
    url: str, *, token: str | None, payload: dict[str, Any] | None = None, timeout: float = 45.0
) -> tuple[int, dict[str, Any]]:
    headers = {'Accept': 'application/json'}
    data = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(payload).encode()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {'error': {'message': body[:200]}}
        return exc.code, parsed


def probe_openai_endpoint(base_url: str, key: str, model: str) -> int:
    url = base_url.rstrip('/') + '/chat/completions'
    started = time.monotonic()
    status, body = _request(
        url,
        token=key,
        payload={
            'model': model,
            'messages': [{'role': 'user', 'content': 'Reply with the single word: ready'}],
            'max_tokens': 16,
        },
    )
    elapsed = time.monotonic() - started
    if status != 200:
        message = (body.get('error') or {}).get('message') or body
        print(f'FAIL {status} in {elapsed:.2f}s: {message}')
        return 2
    choice = (body.get('choices') or [{}])[0]
    content = (choice.get('message') or {}).get('content') or ''
    usage = body.get('usage') or {}
    print(
        'OK endpoint answered in {:.2f}s model={} prompt_tokens={} completion_tokens={}'.format(
            elapsed,
            body.get('model', model),
            usage.get('prompt_tokens'),
            usage.get('completion_tokens'),
        )
    )
    print(f'   reply: {content.strip()[:60]!r}')
    return 0


def probe_hf(token: str, model: str) -> int:
    status, whoami = _request(f'{HF_API}/whoami-v2', token=token)
    if status != 200:
        print(f'FAIL token rejected ({status})')
        return 2
    print(f'OK token belongs to {whoami.get("name")} ({whoami.get("type")})')

    status, meta = _request(f'{HF_API}/models/{model}', token=token)
    if status != 200:
        print(f'FAIL model metadata unavailable ({status})')
        return 2
    print(
        'OK repository reachable: private={} gated={} pipeline={}'.format(
            meta.get('private'), meta.get('gated'), meta.get('pipeline_tag')
        )
    )

    status, body = _request(
        HF_ROUTER,
        token=token,
        payload={
            'model': model,
            'messages': [{'role': 'user', 'content': 'ping'}],
            'max_tokens': 8,
        },
    )
    if status == 200:
        print('OK the router serves this model as a chat model')
        return 0
    message = (body.get('error') or {}).get('message') or body
    code = (body.get('error') or {}).get('code')
    print(f'NOT SERVED ({status} {code}): {message}')
    print(
        '   The catalogue must keep this model in preview status until an '
        'OpenAI-compatible endpoint answers; run endpoint mode against it.'
    )
    return 0


def main() -> int:
    if '--endpoint' in sys.argv:
        url = os.environ.get('CORTEX_VERIFY_PROVIDER_URL', '').strip()
        key = os.environ.get('CORTEX_VERIFY_PROVIDER_KEY', '').strip()
        model = os.environ.get('CORTEX_VERIFY_MODEL', '').strip()
        missing = [
            name
            for name, value in (
                ('CORTEX_VERIFY_PROVIDER_URL', url),
                ('CORTEX_VERIFY_PROVIDER_KEY', key),
                ('CORTEX_VERIFY_MODEL', model),
            )
            if not value
        ]
        if missing:
            print(f'FAIL missing environment variables: {", ".join(missing)}')
            return 1
        return probe_openai_endpoint(url, key, model)

    token = os.environ.get('CORTEX_VERIFY_HF_TOKEN', '').strip()
    if not token:
        print('FAIL set CORTEX_VERIFY_HF_TOKEN, or pass --endpoint')
        return 1
    model = os.environ.get('CORTEX_VERIFY_HF_MODEL', 'Frankenstein-Labs/Cortex.0').strip()
    return probe_hf(token, model)


if __name__ == '__main__':
    raise SystemExit(main())
