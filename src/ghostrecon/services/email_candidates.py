import re
import unicodedata

from ghostrecon.models.api import EmailCandidate

_SEPARATORS = (".", "", "_", "-")


def generate_email_candidates(
    full_name: str, domain: str, known_patterns: list[str] | None = None
) -> list[EmailCandidate]:
    """Generate likely corporate email candidates from a visible business contact."""

    first, *middle_and_last = _name_parts(full_name)
    if not first or not middle_and_last:
        return []
    last = middle_and_last[-1]
    first_initial = first[0]
    last_initial = last[0]

    patterns = known_patterns or [
        "{first}{sep}{last}",
        "{first_initial}{last}",
        "{first}{last_initial}",
        "{first}",
        "{last}{first_initial}",
    ]

    candidates: dict[str, EmailCandidate] = {}
    for pattern in patterns:
        for sep in _SEPARATORS:
            local = pattern.format(
                first=first,
                last=last,
                first_initial=first_initial,
                last_initial=last_initial,
                sep=sep,
            )
            local = re.sub(r"[^a-z0-9._-]", "", local.lower()).strip("._-")
            if not local:
                continue
            email = f"{local}@{domain.lower().strip()}"
            candidates[email] = EmailCandidate(email=email, pattern=pattern)

    return list(candidates.values())


def _name_parts(full_name: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", full_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return [part.lower() for part in re.findall(r"[a-zA-Z]+", ascii_name)]
