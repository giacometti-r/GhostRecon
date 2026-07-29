from enum import StrEnum


class LeadSourceType(StrEnum):
    CRM = "crm"
    FORM = "form"
    CSV = "csv"
    CRAWL = "crawl"
    MANUAL = "manual"
    CYBER_EVENT = "cyber_event"
    SECURITY_INCIDENT = "security_incident"


class OriginType(StrEnum):
    CYBER_EVENT = "cyber_event"
    EVENT_PARTICIPANT = "event_participant"
    SECURITY_INCIDENT = "security_incident"
    MANUAL = "manual"
