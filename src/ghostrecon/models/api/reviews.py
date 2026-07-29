from enum import StrEnum


class ReviewCandidateType(StrEnum):
    ENTITY_RESOLUTION = "entity_resolution"
    CONTACT_ENRICHMENT = "contact_enrichment"
    EMAIL_VERIFICATION = "email_verification"
    SCORING = "scoring"
    INCIDENT_CORROBORATION = "incident_corroboration"


class ReviewCandidateStatus(StrEnum):
    OPEN = "open"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecisionAction(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
