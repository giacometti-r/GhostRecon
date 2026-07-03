import hashlib
import hmac

from ghostrecon.common.security import verify_attio_signature


def test_verify_attio_signature_accepts_valid_hmac() -> None:
    body = b'{"event":"record.created"}'
    hmac_key = "unit-test-key"
    signature = hmac.new(hmac_key.encode(), body, hashlib.sha256).hexdigest()

    assert verify_attio_signature(body, signature, hmac_key) is True


def test_verify_attio_signature_rejects_invalid_hmac() -> None:
    assert verify_attio_signature(b"{}", "bad", "secret") is False
