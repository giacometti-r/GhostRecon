import hmac


def constant_time_token_check(actual: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    return hmac.compare_digest(actual, expected)
