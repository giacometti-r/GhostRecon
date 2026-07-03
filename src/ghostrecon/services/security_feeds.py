from datetime import UTC, datetime
from typing import Any

import httpx

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
NVD_CVE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


async def fetch_cisa_kev() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(CISA_KEV_URL)
        response.raise_for_status()
        payload = response.json()
    return list(payload.get("vulnerabilities", []))


async def fetch_nvd_cves_for_keyword(keyword: str, max_results: int = 20) -> list[dict[str, Any]]:
    params = {
        "keywordSearch": keyword,
        "noRejected": "",
        "resultsPerPage": min(max_results, 100),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(NVD_CVE_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    return list(payload.get("vulnerabilities", []))


def map_security_signal(raw: dict[str, Any], source: str) -> dict[str, object]:
    if source == "cisa-kev":
        return {
            "signal_type": "kev",
            "signal_source": source,
            "signal_strength": 25,
            "signal_topic": raw.get("vulnerabilityName") or raw.get("cveID"),
            "signal_timestamp": raw.get("dateAdded") or datetime.now(UTC).isoformat(),
            "product_relevance": raw.get("knownRansomwareCampaignUse"),
            "raw": raw,
        }
    return {
        "signal_type": "cve",
        "signal_source": source,
        "signal_strength": 10,
        "signal_topic": raw.get("cve", {}).get("id"),
        "signal_timestamp": datetime.now(UTC).isoformat(),
        "raw": raw,
    }
