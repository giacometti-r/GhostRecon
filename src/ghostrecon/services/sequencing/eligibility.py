from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast

from ghostrecon.models.api import (
    SequenceEligibilityRequest,
    SequenceEligibilityResult,
)


def _fuzzy(column: Any, value: str | None) -> Any:
    text = str(value or "").strip()
    return cast(column, String).ilike(f"%{text}%")


def evaluate_sequence_eligibility(request: SequenceEligibilityRequest) -> SequenceEligibilityResult:
    reasons: list[str] = []
    requires_approval = False

    if not request.suppression.allowed:
        return SequenceEligibilityResult(
            eligible=False,
            next_action="suppress",
            requires_approval=False,
            reasons=[request.suppression.reason or "Suppression rule blocked outreach"],
        )

    if not request.score.threshold_met:
        return SequenceEligibilityResult(
            eligible=False,
            next_action="nurture",
            requires_approval=False,
            reasons=request.score.reasons,
        )

    if request.contact.get("strategic_account") or request.score.composite_score >= 85:
        requires_approval = True
        reasons.append("Strategic or high-score contact requires human approval")

    return SequenceEligibilityResult(
        eligible=True,
        next_action="request_approval" if requires_approval else "enroll",
        requires_approval=requires_approval,
        reasons=reasons or ["Eligible for sequence enrollment"],
    )
