from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
)


class AccountIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    company_name: str
    crm_account_id: str | None = None
    hq_country: str | None = None
    employee_count: int | None = Field(default=None, ge=0)
    industry: str | None = None
    named_account_flag: bool = False


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str | None = None
    full_name: str
    title: str | None = None
    email: EmailStr | None = None
    linkedin_url: HttpUrl | None = None
    source_url: HttpUrl | None = None


class DomainEnrichmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    crawl: bool = True
    max_pages: int = Field(default=20, ge=1, le=100)


class DomainEnrichmentResult(BaseModel):
    domain: str
    mx_records: list[str] = []
    nameservers: list[str] = []
    website_title: str | None = None
    security_signals: list[dict[str, object]] = []
    discovered_contacts: list[dict[str, object]] = []


class EmailCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str
    domain: str
    known_patterns: list[str] = []


class EmailCandidate(BaseModel):
    email: EmailStr
    pattern: str
