import hashlib
import hmac


def verify_attio_signature(body: bytes, signature: str | None, secret: str | None) -> bool:
    """Verify Attio webhook HMAC-SHA256 signatures.

    When no secret is configured, verification is disabled for local development only.
    Production deployments should always set GHOSTRECON_ATTIO_WEBHOOK_SECRET.
    """

    if not secret:
        return True
    if not signature:
        return False

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def constant_time_token_check(actual: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    return hmac.compare_digest(actual, expected)
