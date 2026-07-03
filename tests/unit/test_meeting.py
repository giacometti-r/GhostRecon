from ghostrecon.models.api import PrepPacketRequest
from ghostrecon.services.meeting import build_prep_packet


def test_build_prep_packet_includes_stakeholders_and_signals() -> None:
    packet = build_prep_packet(
        PrepPacketRequest(
            account={"company_name": "ExampleCo"},
            contacts=[{"full_name": "Ada Lovelace", "title": "CISO"}],
            signals=[{"signal_type": "kev", "signal_topic": "Known exploited vulnerability"}],
        )
    )

    assert "ExampleCo" in packet.account_summary
    assert packet.stakeholder_map == ["Ada Lovelace - CISO"]
    assert packet.likely_security_priorities == ["Known exploited vulnerability"]
