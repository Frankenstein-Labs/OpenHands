from __future__ import annotations

import hashlib
import hmac


class WebhookSignatureError(Exception):
    pass


def verify_webhook_signature(secret: str, body: bytes, signature_header: str | None) -> None:
    if not secret:
        raise WebhookSignatureError('webhook secret is not configured')
    if not signature_header or not signature_header.startswith('sha256='):
        raise WebhookSignatureError('missing signature')
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise WebhookSignatureError('invalid signature')
