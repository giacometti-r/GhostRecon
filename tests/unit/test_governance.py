from ghostrecon.models.api import SuppressionCheckRequest
from ghostrecon.services.governance import evaluate_suppression


def test_blocks_role_based_email() -> None:
    result = evaluate_suppression(SuppressionCheckRequest(email="admin@example.com"))

    assert result.allowed is False
    assert "Role-based" in (result.reason or "")


def test_allows_supported_non_role_email() -> None:
    result = evaluate_suppression(SuppressionCheckRequest(email="ada@example.com"))

    assert result.allowed is True
