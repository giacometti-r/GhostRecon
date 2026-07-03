from ghostrecon.models.api import PrepPacket, PrepPacketRequest


def build_prep_packet(request: PrepPacketRequest) -> PrepPacket:
    account_name = str(
        request.account.get("company_name") or request.account.get("domain") or "Account"
    )
    contacts = [
        f"{contact.get('full_name', 'Unknown')} - {contact.get('title', 'Unknown role')}"
        for contact in request.contacts
    ]
    signal_topics = [
        str(signal.get("signal_topic") or signal.get("signal_type"))
        for signal in request.signals
        if signal.get("signal_topic") or signal.get("signal_type")
    ]

    return PrepPacket(
        account_summary=f"{account_name} has {len(request.contacts)} known stakeholders and "
        f"{len(request.signals)} active signals.",
        stakeholder_map=contacts,
        likely_security_priorities=signal_topics[:5] or ["Confirm current security priorities"],
        suggested_questions=[
            "Which security initiatives are funded this quarter?",
            "What tools or processes are creating the most operational drag?",
            "Which integrations or controls must be validated before a pilot?",
        ],
        risks=[
            "Signal relevance needs human validation before use in messaging",
            "Technical fit should be confirmed by AE/SE discovery",
        ],
    )
