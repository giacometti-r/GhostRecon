from __future__ import annotations

from string import Formatter

from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
)


def _domain_from_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].lower()


def _crm_target_summary(target: CrmTarget | None) -> str | None:
    if target is None:
        return None
    parts = [target.target_type.replace("_", " "), target.target_id]
    if target.origin_type:
        parts.append(f"from {target.origin_type.replace('_', ' ')}")
    return " · ".join(str(part) for part in parts if part)


def _render_template(template: str, contact: Contact, account: Account | None) -> str:
    values = {
        "contact_full_name": contact.full_name,
        "contact_first_name": contact.full_name.split(" ", 1)[0] if contact.full_name else "",
        "contact_title": contact.title or "",
        "account_company_name": account.company_name if account else "",
        "account_domain": account.domain if account else "",
    }
    used = {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}
    if not used:
        return template
    return template.format_map(_SafeFormat(values))


class _SafeFormat(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""
