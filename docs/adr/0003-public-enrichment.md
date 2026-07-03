# ADR 0003 - Public Enrichment Without Paid APIs

## Status

Accepted.

## Context

The platform should not depend on ZoomInfo, Apollo, Clay, 6sense, or other paid enrichment APIs for v1. Intelligence-first acquisition also creates stricter source-permission and evidence requirements for event participants and incident contacts.

## Decision

Use public, bounded, compliance-aware enrichment:

- Scrapy for allowlisted company-page crawling.
- DNS, MX, RDAP, TLS, website metadata.
- CISA KEV and NVD feeds for cybersecurity context.
- `umuterturk/email-verifier` for syntax/domain/MX/disposable/role-based validation.
- Published event participants only when the source explicitly permits reuse.
- Public business contacts in security, IT, risk, and communications roles for eligible incident companies.


## Consequences

- Lower direct vendor cost.
- Lower contact coverage than paid databases.
- Stronger need for source lineage, human review, and compliance controls.
- Source-level reuse policy becomes an enforceable input to enrichment rather than descriptive metadata.
- Candidate email generation remains separate from verification, CRM approval, and outreach approval.
