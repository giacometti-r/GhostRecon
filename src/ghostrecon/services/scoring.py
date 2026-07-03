from ghostrecon.models.api import ScoreRequest, ScoreResult


def score_lead(request: ScoreRequest) -> ScoreResult:
    account = request.account
    signals = request.signals

    reasons: list[str] = []
    fit_score = 0
    intent_score = 0

    if account.get("named_account_flag"):
        fit_score += 30
        reasons.append("Named account")
    if account.get("employee_count") and int(account["employee_count"]) >= 250:
        fit_score += 20
        reasons.append("Employee count matches target segment")
    if account.get("security_stack") or account.get("tech_stack"):
        fit_score += 20
        reasons.append("Technographic context available")
    if account.get("industry"):
        fit_score += 20
        reasons.append("Industry present")

    for signal in signals:
        strength = int(signal.get("signal_strength", 0))
        intent_score += min(max(strength, 0), 35)
        if signal.get("signal_type") in {"kev", "cve", "intent_surge"}:
            reasons.append(f"Relevant signal: {signal.get('signal_type')}")

    fit_score = min(fit_score, 100)
    intent_score = min(intent_score, 100)
    composite_score = round((fit_score * 0.55) + (intent_score * 0.45))
    threshold_met = composite_score >= 60

    if not threshold_met:
        reasons.append("Composite score below routing threshold")

    return ScoreResult(
        fit_score=fit_score,
        intent_score=intent_score,
        composite_score=composite_score,
        threshold_met=threshold_met,
        reasons=reasons,
    )
