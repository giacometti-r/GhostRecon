from __future__ import annotations

import re
from urllib.parse import urlsplit


def _append_unique(values: list[object] | None, value: object) -> list[object]:
    resolved = list(values or [])
    if value not in resolved:
        resolved.append(value)
    return resolved


def _merge_list(left: list[object] | None, right: list[object] | None) -> list[object]:
    merged = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


def _companies_from_metadata(metadata: dict[str, object]) -> list[object]:
    values = metadata.get("affected_companies")
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    return []


def _companies_from_text(text: str) -> list[object]:
    disclosure_verbs = "reports|reported|discloses|disclosed|confirms|confirmed|suffers|suffered"
    incident_terms = "breach|ransomware|cyberattack|cyber attack"
    patterns = [
        rf"([A-Z][A-Za-z0-9&., ]{{2,80}}?) (?:{disclosure_verbs})",
        rf"(?:{incident_terms}) (?:at|hits|against) ([A-Z][A-Za-z0-9&., ]{{2,80}})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            company = match.group(1).strip(" .,:")
            if company:
                return [company]
    return []


def _domains_from_metadata(metadata: dict[str, object]) -> list[object]:
    values = metadata.get("affected_domains")
    if isinstance(values, list):
        return [str(value).strip().lower() for value in values if str(value).strip()]
    return []


def _incident_contexts(
    companies: list[object] | None, domains: list[object] | None
) -> list[tuple[str | None, str | None]]:
    company_values = [str(value).strip() for value in companies or [] if str(value).strip()]
    domain_values = [str(value).strip().lower() for value in domains or [] if str(value).strip()]
    if company_values:
        contexts: list[tuple[str | None, str | None]] = []
        for index, company in enumerate(company_values):
            domain = domain_values[index] if index < len(domain_values) else None
            if domain is None and len(domain_values) == 1:
                domain = domain_values[0]
            contexts.append((company, domain))
        return contexts
    if domain_values:
        return [(None, domain) for domain in domain_values]
    return [(None, None)]


def _attack_vector(lowered: str) -> str | None:
    for term, value in _ATTACK_VECTORS.items():
        if term in lowered:
            return value
    return None


def _watch_target_key(target_type: str, key: str) -> str:
    text = key.strip().lower()
    if target_type == "domain":
        return _hostname(f"https://{text}") or text
    return _slug(text)


def _hostname(url: str | None) -> str | None:
    if not url:
        return None
    return (urlsplit(url).hostname or "").lower() or None


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


from .candidates import _ATTACK_VECTORS  # noqa: E402
