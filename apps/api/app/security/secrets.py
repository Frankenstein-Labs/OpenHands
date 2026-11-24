from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings


class SecretBoxUnavailable(RuntimeError):
    """No usable encryption key is configured."""


class SecretDecryptError(RuntimeError):
    """A stored secret cannot be decrypted with the configured key."""


class SecretBox:
    """Symmetric encryption for tenant provider keys.

    Keys never leave the server: the browser sends a plaintext key once over
    TLS, the API encrypts it, and only ciphertext reaches Postgres. There is no
    plaintext fallback — if the key is missing the gateway refuses to store
    anything rather than write an unprotected credential.
    """

    def __init__(self, key: str | None) -> None:
        if not key:
            raise SecretBoxUnavailable('CORTEX_SECRET_KEY is not configured')
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise SecretBoxUnavailable('CORTEX_SECRET_KEY is not a valid Fernet key') from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise SecretDecryptError('stored credential cannot be decrypted') from exc


def get_secret_box(settings: Settings | None = None) -> SecretBox:
    return SecretBox((settings or get_settings()).secret_key)
