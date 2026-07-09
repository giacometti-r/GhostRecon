from __future__ import annotations

from datetime import UTC, datetime, timedelta
from string import Formatter
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CrmProspectList,
    CrmProspectOut,
    InboundEmailEventCreate,
    InboundEmailEventOut,
    InboundEmailEventType,
    OutboundEmailOut,
    SequenceActivityActionRequest,
    SequenceActivityList,
    SequenceActivityOut,
    SequenceActivityScheduleMeetingRequest,
    SequenceCreateRequest,
    SequenceCrmProspectImportRequest,
    SequenceEligibilityRequest,
    SequenceEligibilityResult,
    SequenceEmailAlertCreate,
    SequenceEmailAlertOut,
    SequenceEnrollmentActionRequest,
    SequenceEnrollmentCreateRequest,
    SequenceEnrollmentList,
    SequenceEnrollmentOut,
    SequenceList,
    SequenceOut,
    SequenceStepOut,
    SequenceUpdateRequest,
    SuppressionCheckRequest,
    UnsubscribeRequest,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    EmailCandidateRecord,
    InboundEmailEvent,
    OutboundEmail,
    OutboxEvent,
    Sequence,
    SequenceEmailAlert,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepActivity,
    SequenceSuppressionEvent,
    Suppression,
)
from ghostrecon.services.crm_exports import crm_client_for_settings
from ghostrecon.services.governance import evaluate_suppression
from ghostrecon.services.sequence_adapters import (
    ImapPoller,
    SmtpSender,
    SmtpSendRequest,
    StdlibImapPoller,
    StdlibSmtpSender,
)

SEQUENCING_SERVICE_NAME = "sequencing-service"
ACTIVE_ENROLLMENT_STATUSES = {"active"}
TERMINAL_ENROLLMENT_STATUSES = {"completed", "canceled", "suppressed", "failed"}


def evaluate_sequence_eligibility(request: SequenceEligibilityRequest) -> SequenceEligibilityResult:
    reasons: list[str] = []
    requires_approval = False

    if not request.suppression.allowed:
        return SequenceEligibilityResult(
            eligible=False,
            next_action="suppress",
            requires_approval=False,
            reasons=[request.suppression.reason or "Suppression rule blocked outreach"],
        )

    if not request.score.threshold_met:
        return SequenceEligibilityResult(
            eligible=False,
            next_action="nurture",
            requires_approval=False,
            reasons=request.score.reasons,
        )

    if request.contact.get("strategic_account") or request.score.composite_score >= 85:
        requires_approval = True
        reasons.append("Strategic or high-score contact requires human approval")

    return SequenceEligibilityResult(
        eligible=True,
        next_action="request_approval" if requires_approval else "enroll",
        requires_approval=requires_approval,
        reasons=reasons or ["Eligible for sequence enrollment"],
    )


async def create_sequence(
    request: SequenceCreateRequest,
    *,
    actor: str,
    idempotency_key: str | None = None,
    settings: Settings | None = None,
) -> SequenceOut:
    _ = actor
    async with session_scope(settings) as session:
        if idempotency_key:
            existing = await session.scalar(
                select(Sequence).where(Sequence.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return sequence_to_model(existing, await _sequence_steps(session, existing.id))

        now = utcnow()
        sequence = Sequence(
            name=request.name,
            owner_id=request.owner_id,
            channel=request.channel.value,
            status="active",
            rate_limit_policy=dict(request.rate_limit_policy),
            definition_version=1,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        session.add(sequence)
        await session.flush()
        steps: list[SequenceStep] = []
        for index, step_request in enumerate(request.steps, start=1):
            step = SequenceStep(
                sequence_id=sequence.id,
                step_order=step_request.step_order or index,
                channel=step_request.channel.value,
                delay_seconds=step_request.delay_seconds,
                subject_template=step_request.subject_template,
                body_template=step_request.body_template,
                requires_approval=_requires_approval(
                    step_request.channel.value,
                    step_request.requires_approval,
                ),
                step_metadata=dict(step_request.step_metadata),
                definition_version=sequence.definition_version,
                active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(step)
            steps.append(step)
        await session.flush()
        return sequence_to_model(sequence, sorted(steps, key=lambda item: item.step_order))


async def list_sequences(
    *,
    status: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> SequenceList:
    async with session_scope(settings) as session:
        query = select(Sequence).order_by(Sequence.created_at.desc()).limit(limit)
        if status:
            query = query.where(Sequence.status == status)
        result = await session.execute(query)
        sequences = [
            sequence_to_model(sequence, await _sequence_steps(session, sequence.id))
            for sequence in result.scalars()
        ]
        return SequenceList(sequences=sequences)


async def get_sequence(
    sequence_id: str,
    *,
    settings: Settings | None = None,
) -> SequenceOut | None:
    async with session_scope(settings) as session:
        sequence = await session.get(Sequence, sequence_id)
        if sequence is None:
            return None
        return sequence_to_model(sequence, await _sequence_steps(session, sequence.id))


async def update_sequence(
    sequence_id: str,
    request: SequenceUpdateRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceOut | None:
    _ = actor
    async with session_scope(settings) as session:
        sequence = await session.get(Sequence, sequence_id)
        if sequence is None:
            return None
        now = utcnow()
        if request.name is not None:
            sequence.name = request.name
        if request.owner_id is not None:
            sequence.owner_id = request.owner_id
        if request.channel is not None:
            sequence.channel = request.channel.value
        if request.status is not None:
            sequence.status = request.status.value
        if request.rate_limit_policy is not None:
            sequence.rate_limit_policy = dict(request.rate_limit_policy)
        if request.steps is not None:
            if (
                request.expected_version is not None
                and request.expected_version != sequence.definition_version
            ):
                raise ValueError("sequence definition version conflict")
            sequence.definition_version += 1
            for index, step_request in enumerate(request.steps, start=1):
                order = step_request.step_order or index
                session.add(
                    SequenceStep(
                        sequence_id=sequence.id,
                        step_order=order,
                        channel=step_request.channel.value,
                        delay_seconds=step_request.delay_seconds,
                        subject_template=step_request.subject_template,
                        body_template=step_request.body_template,
                        requires_approval=_requires_approval(
                            step_request.channel.value,
                            step_request.requires_approval,
                        ),
                        step_metadata=dict(step_request.step_metadata),
                        definition_version=sequence.definition_version,
                        active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
        sequence.updated_at = now
        await session.flush()
        return sequence_to_model(sequence, await _sequence_steps(session, sequence.id))


async def create_sequence_enrollment(
    request: SequenceEnrollmentCreateRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut:
    if not request.outreach_approved:
        raise ValueError("separate outreach approval is required")

    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(SequenceEnrollment).where(
                SequenceEnrollment.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return await _enrollment_to_model_with_emails(session, existing)

        sequence = await session.get(Sequence, request.sequence_id)
        if sequence is None or sequence.status != "active":
            raise ValueError("active sequence not found")
        steps = await _sequence_steps(session, sequence.id)
        if not steps:
            raise ValueError("sequence has no active steps")

        target = await session.get(CrmTarget, request.crm_target_id)
        if target is None:
            raise ValueError("crm target not found")
        if target.status != "exported" or target.export_status != "exported":
            raise ValueError("crm target must be exported before sequence enrollment")

        contact = await _contact_for_target(session, target, request.contact_id)
        _require_sendable_contact(contact)
        account_id = request.account_id or contact.account_id
        domain = _domain_from_email(contact.email)
        suppression = await _suppression_allowed(
            session,
            email=contact.email,
            domain=domain,
            contact_id=contact.id,
            channel=sequence.channel,
        )
        if not suppression.allowed:
            raise ValueError(suppression.reason or "suppression blocks outreach")

        now = utcnow()
        policy_snapshot = dict(target.policy_snapshot or {})
        policy_snapshot.update(dict(request.policy_snapshot))
        enrollment = SequenceEnrollment(
            sequence_id=sequence.id,
            crm_target_id=target.id,
            contact_id=contact.id,
            account_id=account_id,
            status="active",
            approval_actor=actor,
            approval_reason=request.approval_reason,
            current_step_order=steps[0].step_order,
            definition_version=sequence.definition_version,
            next_step_at=request.start_at or now,
            pause_reason=None,
            policy_snapshot=policy_snapshot,
            idempotency_key=idempotency_key,
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(enrollment)
        await session.flush()
        _enqueue_event(
            session,
            EventName.SEQUENCE_ENROLLED,
            "sequence_enrollment",
            enrollment.id,
            sequence_enrollment_to_api(enrollment),
            f"sequence.enrolled:{enrollment.id}",
        )
        return await _enrollment_to_model_with_emails(session, enrollment)


async def get_sequence_enrollment(
    enrollment_id: str,
    *,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        return await _enrollment_to_model_with_emails(session, enrollment)


async def list_sequence_enrollments(
    *,
    status: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> SequenceEnrollmentList:
    async with session_scope(settings) as session:
        query = (
            select(SequenceEnrollment)
            .order_by(SequenceEnrollment.created_at.desc())
            .limit(limit)
        )
        if status:
            query = query.where(SequenceEnrollment.status == status)
        result = await session.execute(query)
        enrollments = [
            await _enrollment_to_model_with_emails(session, enrollment)
            for enrollment in result.scalars()
        ]
        return SequenceEnrollmentList(enrollments=enrollments)


async def list_sequence_activities(
    *,
    status: str | None = None,
    channel: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> SequenceActivityList:
    async with session_scope(settings) as session:
        query = (
            select(SequenceStepActivity)
            .order_by(SequenceStepActivity.created_at.desc())
            .limit(limit)
        )
        if status:
            query = query.where(SequenceStepActivity.status == status)
        if channel:
            query = query.where(SequenceStepActivity.channel == channel)
        result = await session.execute(query)
        activities = [
            await _activity_to_model_with_display(session, activity)
            for activity in result.scalars()
        ]
        return SequenceActivityList(activities=activities)


async def complete_sequence_activity(
    activity_id: str,
    request: SequenceActivityActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceActivityOut | None:
    async with session_scope(settings) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            return None
        if activity.status not in {"pending", "scheduled"}:
            raise ValueError(f"cannot complete {activity.status} activity")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        step = await session.get(SequenceStep, activity.sequence_step_id)
        if enrollment is None or step is None:
            raise ValueError("activity is missing sequence context")
        now = utcnow()
        activity.status = "completed"
        activity.completed_by = actor
        activity.completed_at = now
        activity.metadata_payload = {
            **dict(activity.metadata_payload or {}),
            **dict(request.metadata),
            "completion_reason": request.reason,
        }
        activity.updated_at = now
        await _advance_enrollment(session, enrollment, step)
        return await _activity_to_model_with_display(session, activity)


async def schedule_sequence_meeting_activity(
    activity_id: str,
    request: SequenceActivityScheduleMeetingRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceActivityOut | None:
    async with session_scope(settings) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            return None
        if activity.channel != "google_meet":
            raise ValueError("activity is not a Google Meet step")
        if activity.status not in {"pending", "scheduled"}:
            raise ValueError(f"cannot schedule {activity.status} activity")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        if enrollment is None:
            raise ValueError("activity is missing enrollment")
        metadata = dict(activity.metadata_payload or {})
        meeting_context = {
            "crm_target_id": enrollment.crm_target_id,
            "sequence_enrollment_id": enrollment.id,
            "account_id": enrollment.account_id,
            "contact_id": enrollment.contact_id,
            "policy_snapshot": dict(enrollment.policy_snapshot or {}),
        }

    from ghostrecon.models.api import MeetingCreateRequest
    from ghostrecon.services.meeting import create_meeting

    meeting = await create_meeting(
        MeetingCreateRequest(
            crm_target_id=str(meeting_context["crm_target_id"]),
            sequence_enrollment_id=str(meeting_context["sequence_enrollment_id"]),
            account_id=meeting_context["account_id"],
            contact_id=meeting_context["contact_id"],
            subject=request.subject or str(metadata.get("meeting_subject") or "Security discovery"),
            description=request.description or str(metadata.get("meeting_description") or ""),
            location=request.location,
            start_at=request.start_at,
            end_at=request.end_at,
            timezone=request.timezone,
            attendees=request.attendees,
            policy_snapshot=dict(meeting_context["policy_snapshot"]),
            send_updates=request.send_updates,
        ),
        actor=actor,
        idempotency_key=f"sequence-meeting:{activity_id}",
        settings=settings,
    )
    async with session_scope(settings) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            raise ValueError("activity disappeared during meeting scheduling")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        step = await session.get(SequenceStep, activity.sequence_step_id)
        if enrollment is None or step is None:
            raise ValueError("activity disappeared during meeting scheduling")
        now = utcnow()
        activity.meeting_handoff_id = meeting.id
        activity.status = "scheduled"
        activity.completed_by = actor
        activity.completed_at = now
        activity.updated_at = now
        await _advance_enrollment(session, enrollment, step)
        return await _activity_to_model_with_display(session, activity)


async def search_crm_prospects(
    *,
    query: str,
    limit: int = 25,
    settings: Settings | None = None,
) -> CrmProspectList:
    resolved = settings or get_settings()
    client = crm_client_for_settings(resolved)
    prospects = await client.search_prospects(query, limit=limit)
    return CrmProspectList(
        prospects=[
            CrmProspectOut(
                provider_record_id=prospect.provider_record_id,
                provider_object=prospect.provider_object,
                display_name=prospect.display_name,
                email=prospect.email,
                title=prospect.title,
                company_name=prospect.company_name,
                company_domain=prospect.company_domain,
                source_payload=dict(prospect.source_payload),
            )
            for prospect in prospects
            if prospect.provider_record_id
        ],
        provider="attio" if resolved.attio_access_token else "local-demo",
    )


async def import_crm_prospect_to_sequence(
    request: SequenceCrmProspectImportRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut:
    if not request.outreach_approved:
        raise ValueError("separate outreach approval is required")
    resolved = settings or get_settings()
    client = crm_client_for_settings(resolved)
    prospect = await client.get_prospect(request.provider_record_id)
    if prospect is None:
        matches = await client.search_prospects(request.provider_record_id, limit=25)
        prospect = next(
            (
                candidate
                for candidate in matches
                if candidate.provider_record_id == request.provider_record_id
            ),
            None,
        )
    if prospect is None:
        raise ValueError("CRM prospect not found")
    if not prospect.email:
        raise ValueError("CRM prospect requires an email before sequence assignment")
    domain = (
        prospect.company_domain
        or _domain_from_email(prospect.email)
        or "unknown.local"
    ).lower()
    now = utcnow()
    async with session_scope(resolved) as session:
        account = await session.scalar(select(Account).where(Account.domain == domain).limit(1))
        if account is None:
            account = Account(
                crm_account_id=f"crm-account:{domain}",
                domain=domain,
                company_name=prospect.company_name or domain,
                hq_country=None,
                employee_count=None,
                revenue_band=None,
                industry=None,
                sub_industry=None,
                tech_stack={},
                security_stack={},
                intent_topics=[],
                territory=None,
                owner_id=actor,
                named_account_flag=False,
                priority_tier=None,
                fit_score=0,
                intent_score=0,
                composite_score=0,
                last_signal_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(account)
            await session.flush()
        contact = await session.scalar(
            select(Contact)
            .where(Contact.account_id == account.id)
            .where(Contact.email == prospect.email.lower())
            .limit(1)
        )
        if contact is None:
            contact = Contact(
                crm_contact_id=prospect.provider_record_id,
                account_id=account.id,
                full_name=prospect.display_name,
                title=prospect.title,
                seniority=None,
                function="security",
                email=prospect.email.lower(),
                email_status="verified",
                phone=None,
                linkedin_url=None,
                timezone=None,
                persona_type="security_leader",
                buying_role=None,
                last_enriched_at=now,
                do_not_contact_flag=False,
                lawful_basis="legitimate_interest",
                source_vendor="attio" if resolved.attio_access_token else "local-demo-crm",
                source_confidence=80,
                source_url=None,
                source_definition_id=None,
                source_item_ids=[],
                origin_type="manual",
                origin_id=prospect.provider_record_id,
                source_policy_snapshot={"source": "crm_import"},
                review_status="not_required",
                review_reason=None,
                idempotency_key=f"crm-import-contact:{prospect.provider_record_id}",
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(contact)
            await session.flush()
        target_key = f"crm-import-target:{prospect.provider_record_id}"
        target = await session.scalar(
            select(CrmTarget).where(CrmTarget.idempotency_key == target_key)
        )
        if target is None:
            target = CrmTarget(
                review_candidate_id=None,
                review_decision_id=None,
                target_type="contact",
                target_id=contact.id,
                origin_type="manual",
                origin_id=prospect.provider_record_id,
                source_definition_id=None,
                source_item_ids=[],
                status="exported",
                export_status="exported",
                policy_snapshot={"source": "crm_import", **dict(request.policy_snapshot)},
                approval_snapshot={
                    "approved_by": actor,
                    "approval_reason": request.approval_reason,
                },
                idempotency_key=target_key,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(target)
            await session.flush()
        account_id = account.id
        contact_id = contact.id
        target_id = target.id
    return await create_sequence_enrollment(
        SequenceEnrollmentCreateRequest(
            sequence_id=request.sequence_id,
            crm_target_id=target_id,
            contact_id=contact_id,
            account_id=account_id,
            start_at=request.start_at,
            outreach_approved=True,
            approval_reason=request.approval_reason,
            policy_snapshot=request.policy_snapshot,
        ),
        actor=actor,
        idempotency_key=idempotency_key,
        settings=resolved,
    )


async def pause_sequence_enrollment(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    _ = actor
    return await _set_enrollment_status(
        enrollment_id,
        status="paused",
        reason=request.reason,
        event_name=EventName.SEQUENCE_PAUSED,
        settings=settings,
    )


async def resume_sequence_enrollment(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    _ = actor, request
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        if enrollment.status in TERMINAL_ENROLLMENT_STATUSES:
            raise ValueError(f"cannot resume {enrollment.status} enrollment")
        enrollment.status = "active"
        enrollment.pause_reason = None
        enrollment.next_step_at = enrollment.next_step_at or utcnow()
        enrollment.version += 1
        enrollment.updated_at = utcnow()
        return await _enrollment_to_model_with_emails(session, enrollment)


async def cancel_sequence_enrollment(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    _ = actor
    return await _set_enrollment_status(
        enrollment_id,
        status="canceled",
        reason=request.reason,
        event_name=None,
        settings=settings,
    )


async def create_sequence_email_alert(
    enrollment_id: str,
    request: SequenceEmailAlertCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> SequenceEmailAlertOut | None:
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        existing = await session.scalar(
            select(SequenceEmailAlert).where(
                SequenceEmailAlert.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return sequence_email_alert_to_model(existing)
        alert = SequenceEmailAlert(
            enrollment_id=enrollment.id,
            recipient_email=str(request.recipient_email).lower(),
            subject=request.subject,
            body=request.body,
            send_at=request.send_at or utcnow(),
            status="pending",
            actor=actor,
            idempotency_key=idempotency_key,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(alert)
        await session.flush()
        return sequence_email_alert_to_model(alert)


async def process_due_sequence_email_alerts(
    *,
    limit: int = 50,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    smtp_sender = sender or StdlibSmtpSender(resolved)
    now = utcnow()
    async with session_scope(resolved) as session:
        result = await session.execute(
            select(SequenceEmailAlert)
            .where(SequenceEmailAlert.status == "pending")
            .where(SequenceEmailAlert.send_at <= now)
            .order_by(SequenceEmailAlert.send_at.asc(), SequenceEmailAlert.id.asc())
            .limit(limit)
        )
        alerts = list(result.scalars())
        outcomes: list[dict[str, object]] = []
        for alert in alerts:
            message_id = f"<ghostrecon-alert-{alert.id}@local>"
            try:
                sent = smtp_sender.send(
                    SmtpSendRequest(
                        from_email=resolved.smtp_from_address.lower(),
                        to_email=alert.recipient_email,
                        subject=alert.subject,
                        body=alert.body,
                        message_id=message_id,
                    )
                )
            except Exception as exc:
                alert.status = "failed_retryable"
                alert.last_error = str(exc)
                alert.updated_at = utcnow()
                outcomes.append(
                    {"alert_id": alert.id, "status": alert.status, "reason": str(exc)}
                )
                continue
            alert.status = "sent"
            alert.provider_message_id = sent.provider_message_id
            alert.sent_at = utcnow()
            alert.updated_at = utcnow()
            outcomes.append({"alert_id": alert.id, "status": alert.status})
        return {"processed": len(outcomes), "outcomes": outcomes}


async def process_due_sequence_steps(
    *,
    limit: int = 50,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    now = utcnow()
    async with session_scope(resolved) as session:
        result = await session.execute(
            select(SequenceEnrollment)
            .where(SequenceEnrollment.status.in_(ACTIVE_ENROLLMENT_STATUSES))
            .where(SequenceEnrollment.next_step_at.is_not(None))
            .where(SequenceEnrollment.next_step_at <= now)
            .order_by(SequenceEnrollment.next_step_at)
            .limit(limit)
        )
        enrollment_ids = [enrollment.id for enrollment in result.scalars()]

    outcomes = []
    for enrollment_id in enrollment_ids:
        outcomes.append(
            await send_next_sequence_step(
                enrollment_id,
                settings=resolved,
                sender=sender,
            )
        )
    return {"processed": len(outcomes), "outcomes": outcomes}


async def send_next_sequence_step(
    enrollment_id: str,
    *,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    _ = sender
    async with session_scope(resolved) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            raise ValueError("sequence enrollment not found")
        if enrollment.status != "active":
            return {"enrollment_id": enrollment.id, "status": enrollment.status}

        sequence = await session.get(Sequence, enrollment.sequence_id)
        if sequence is None or sequence.status != "active":
            await _pause_for_policy(session, enrollment, "sequence is not active")
            return {"enrollment_id": enrollment.id, "status": "paused"}

        step = await _step_for_order(
            session,
            enrollment.sequence_id,
            enrollment.current_step_order,
            enrollment.definition_version,
        )
        if step is None:
            _complete_enrollment(session, enrollment)
            return {"enrollment_id": enrollment.id, "status": "completed"}

        contact = await session.get(Contact, enrollment.contact_id)
        if contact is None:
            await _pause_for_policy(session, enrollment, "contact no longer exists")
            return {"enrollment_id": enrollment.id, "status": "paused"}
        try:
            _require_sendable_contact(contact)
        except ValueError as exc:
            await _pause_for_policy(session, enrollment, str(exc))
            return {"enrollment_id": enrollment.id, "status": "paused", "reason": str(exc)}

        domain = _domain_from_email(contact.email)
        suppression = await _suppression_allowed(
            session,
            email=contact.email,
            domain=domain,
            contact_id=contact.id,
            channel=step.channel,
        )
        if not suppression.allowed:
            await _suppress_enrollment(session, enrollment, contact, suppression.reason)
            return {
                "enrollment_id": enrollment.id,
                "status": "suppressed",
                "reason": suppression.reason,
            }

        if step.channel != "email":
            activity = await _activity_for_step(session, enrollment, step, status="pending")
            enrollment.next_step_at = None
            enrollment.updated_at = utcnow()
            return {
                "enrollment_id": enrollment.id,
                "activity_id": activity.id,
                "status": activity.status,
                "channel": activity.channel,
            }

        from_email = resolved.smtp_from_address.lower()
        rate_limit_reason = await _rate_limit_blocker(
            session,
            to_email=contact.email,
            from_email=from_email,
            channel=step.channel,
            sequence=sequence,
            settings=resolved,
        )
        if rate_limit_reason:
            enrollment.next_step_at = utcnow() + timedelta(
                seconds=resolved.sequence_retry_after_seconds
            )
            enrollment.pause_reason = rate_limit_reason
            enrollment.updated_at = utcnow()
            return {
                "enrollment_id": enrollment.id,
                "status": "rate_limited",
                "reason": rate_limit_reason,
            }

        account = (
            await session.get(Account, enrollment.account_id) if enrollment.account_id else None
        )
        outbound = await _outbound_for_step(session, enrollment, step, contact, account, from_email)
        outbound.status = "pending_approval"
        outbound.updated_at = utcnow()
        activity = await _activity_for_step(
            session,
            enrollment,
            step,
            status="pending_approval",
            outbound_email_id=outbound.id,
        )
        enrollment.next_step_at = None
        enrollment.updated_at = utcnow()
        return {
            "enrollment_id": enrollment.id,
            "outbound_email_id": outbound.id,
            "activity_id": activity.id,
            "status": activity.status,
        }


async def send_approved_sequence_email(
    activity_id: str,
    request: SequenceActivityActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> SequenceActivityOut | None:
    _ = request
    resolved = settings or get_settings()
    smtp_sender = sender or StdlibSmtpSender(resolved)
    async with session_scope(resolved) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            return None
        if activity.channel != "email":
            raise ValueError("activity is not an email approval")
        if activity.status not in {"pending_approval", "approved"}:
            raise ValueError(f"cannot approve {activity.status} activity")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        step = await session.get(SequenceStep, activity.sequence_step_id)
        if enrollment is None or step is None:
            raise ValueError("activity is missing sequence context")
        if enrollment.status != "active":
            raise ValueError("sequence enrollment is not active")
        sequence = await session.get(Sequence, enrollment.sequence_id)
        contact = await session.get(Contact, enrollment.contact_id)
        if sequence is None or sequence.status != "active":
            await _pause_for_policy(session, enrollment, "sequence is not active")
            raise ValueError("sequence is not active")
        if contact is None:
            await _pause_for_policy(session, enrollment, "contact no longer exists")
            raise ValueError("contact no longer exists")
        _require_sendable_contact(contact)
        domain = _domain_from_email(contact.email)
        suppression = await _suppression_allowed(
            session,
            email=contact.email,
            domain=domain,
            contact_id=contact.id,
            channel=step.channel,
        )
        if not suppression.allowed:
            await _suppress_enrollment(session, enrollment, contact, suppression.reason)
            raise ValueError(suppression.reason or "suppression blocks outreach")
        from_email = resolved.smtp_from_address.lower()
        rate_limit_reason = await _rate_limit_blocker(
            session,
            to_email=contact.email,
            from_email=from_email,
            channel=step.channel,
            sequence=sequence,
            settings=resolved,
        )
        if rate_limit_reason:
            enrollment.next_step_at = utcnow() + timedelta(
                seconds=resolved.sequence_retry_after_seconds
            )
            enrollment.pause_reason = rate_limit_reason
            enrollment.updated_at = utcnow()
            raise ValueError(rate_limit_reason)
        account = (
            await session.get(Account, enrollment.account_id) if enrollment.account_id else None
        )
        outbound = (
            await session.get(OutboundEmail, activity.outbound_email_id)
            if activity.outbound_email_id
            else await _outbound_for_step(session, enrollment, step, contact, account, from_email)
        )
        outbound.attempt_count += 1
        outbound.status = "pending"
        outbound.last_error = None
        outbound.retry_after_seconds = None
        outbound.updated_at = utcnow()
        message_id = f"<ghostrecon-{outbound.id}@local>"

        try:
            result = smtp_sender.send(
                SmtpSendRequest(
                    from_email=outbound.from_email,
                    to_email=outbound.to_email,
                    subject=outbound.subject,
                    body=outbound.body,
                    message_id=message_id,
                )
            )
        except Exception as exc:
            outbound.status = "failed_retryable"
            outbound.last_error = str(exc)
            outbound.retry_after_seconds = resolved.sequence_retry_after_seconds
            outbound.updated_at = utcnow()
            activity.status = "failed"
            activity.metadata_payload = {
                **dict(activity.metadata_payload or {}),
                "last_error": str(exc),
            }
            activity.updated_at = utcnow()
            enrollment.next_step_at = utcnow() + timedelta(
                seconds=resolved.sequence_retry_after_seconds
            )
            enrollment.updated_at = utcnow()
            return await _activity_to_model_with_display(session, activity)

        outbound.status = "sent"
        outbound.provider_message_id = result.provider_message_id
        outbound.sent_at = utcnow()
        outbound.updated_at = utcnow()
        _enqueue_event(
            session,
            EventName.EMAIL_SENT,
            "outbound_email",
            outbound.id,
            outbound_email_to_api(outbound),
            f"email.sent:{outbound.id}:{outbound.attempt_count}",
        )
        await _advance_enrollment(session, enrollment, step)
        activity.status = "completed"
        activity.approved_by = actor
        activity.approved_at = utcnow()
        activity.completed_by = actor
        activity.completed_at = utcnow()
        activity.updated_at = utcnow()
        return await _activity_to_model_with_display(session, activity)


async def process_inbound_email_event(
    request: InboundEmailEventCreate,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> InboundEmailEventOut:
    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(InboundEmailEvent).where(InboundEmailEvent.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return inbound_event_to_model(existing)

        outbound = await _find_outbound_for_inbound(session, request)
        enrollment = (
            await session.get(SequenceEnrollment, outbound.enrollment_id)
            if outbound is not None
            else await _find_enrollment_by_email(session, request.from_email)
        )
        now = request.occurred_at or utcnow()
        event = InboundEmailEvent(
            enrollment_id=enrollment.id if enrollment else None,
            outbound_email_id=outbound.id if outbound else None,
            event_type=request.event_type.value,
            from_email=str(request.from_email).lower() if request.from_email else None,
            to_email=str(request.to_email).lower() if request.to_email else None,
            message_id=request.message_id,
            provider_payload=dict(request.provider_payload),
            idempotency_key=idempotency_key,
            occurred_at=now,
            created_at=utcnow(),
        )
        session.add(event)
        await session.flush()

        if request.event_type == InboundEmailEventType.REPLY:
            if enrollment:
                _complete_enrollment(session, enrollment)
            _enqueue_event(
                session,
                EventName.REPLY_RECEIVED,
                "inbound_email_event",
                event.id,
                inbound_event_to_api(event),
                f"reply.received:{event.id}",
            )
        elif request.event_type == InboundEmailEventType.BOUNCE:
            if outbound:
                outbound.status = "failed_terminal"
                outbound.last_error = "bounce received"
                outbound.updated_at = utcnow()
            if enrollment:
                enrollment.status = "paused"
                enrollment.pause_reason = "bounce received"
                enrollment.updated_at = utcnow()
            _enqueue_event(
                session,
                EventName.BOUNCE_RECEIVED,
                "inbound_email_event",
                event.id,
                inbound_event_to_api(event),
                f"bounce.received:{event.id}",
            )
        elif request.event_type == InboundEmailEventType.UNSUBSCRIBE:
            email = str(request.from_email or request.to_email or "").lower()
            if email:
                channel = str(request.provider_payload.get("channel") or "email")
                reason = str(request.provider_payload.get("reason") or "unsubscribe")
                await _create_unsubscribe_suppression(
                    session,
                    email=email,
                    channel=channel,
                    reason=reason,
                    source_event=event,
                    enrollment=enrollment,
                )
            if enrollment:
                enrollment.status = "suppressed"
                enrollment.pause_reason = "unsubscribe"
                enrollment.completed_at = utcnow()
                enrollment.updated_at = utcnow()
            _enqueue_event(
                session,
                EventName.UNSUBSCRIBE_RECEIVED,
                "inbound_email_event",
                event.id,
                inbound_event_to_api(event),
                f"unsubscribe.received:{event.id}",
            )
        return inbound_event_to_model(event)


async def process_unsubscribe(
    request: UnsubscribeRequest,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> InboundEmailEventOut:
    return await process_inbound_email_event(
        InboundEmailEventCreate(
            event_type=InboundEmailEventType.UNSUBSCRIBE,
            from_email=request.email,
            provider_payload={
                **dict(request.provider_payload),
                "domain": request.domain,
                "reason": request.reason,
                "channel": request.channel,
            },
        ),
        idempotency_key=idempotency_key,
        settings=settings,
    )


async def poll_inbound_email_events(
    *,
    limit: int = 50,
    settings: Settings | None = None,
    poller: ImapPoller | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    imap_poller = poller or StdlibImapPoller(resolved)
    events = imap_poller.poll(limit=limit)
    processed = []
    for event in events:
        key = f"inbound_email:{event.event_type.value}:{event.message_id or uuid4()}"
        processed.append(
            (await process_inbound_email_event(event, idempotency_key=key, settings=resolved)).id
        )
    return {"processed": len(processed), "event_ids": processed}


def sequence_step_to_model(step: SequenceStep) -> SequenceStepOut:
    return SequenceStepOut(
        id=step.id,
        sequence_id=step.sequence_id,
        step_order=step.step_order,
        channel=step.channel,
        delay_seconds=step.delay_seconds,
        subject_template=step.subject_template,
        body_template=step.body_template,
        requires_approval=step.requires_approval,
        step_metadata=step.step_metadata or {},
        definition_version=step.definition_version,
        active=step.active,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )


def sequence_to_model(sequence: Sequence, steps: list[SequenceStep]) -> SequenceOut:
    return SequenceOut(
        id=sequence.id,
        name=sequence.name,
        owner_id=sequence.owner_id,
        channel=sequence.channel,
        status=sequence.status,
        rate_limit_policy=sequence.rate_limit_policy or {},
        definition_version=sequence.definition_version,
        created_at=sequence.created_at,
        updated_at=sequence.updated_at,
        steps=[sequence_step_to_model(step) for step in steps],
    )


def outbound_email_to_api(outbound: OutboundEmail) -> dict[str, object]:
    return {
        "id": outbound.id,
        "enrollment_id": outbound.enrollment_id,
        "sequence_step_id": outbound.sequence_step_id,
        "contact_id": outbound.contact_id,
        "channel": outbound.channel,
        "to_email": outbound.to_email,
        "from_email": outbound.from_email,
        "subject": outbound.subject,
        "status": outbound.status,
        "provider_message_id": outbound.provider_message_id,
        "attempt_count": outbound.attempt_count,
        "last_error": outbound.last_error,
        "retry_after_seconds": outbound.retry_after_seconds,
        "scheduled_at": outbound.scheduled_at,
        "sent_at": outbound.sent_at,
        "created_at": outbound.created_at,
        "updated_at": outbound.updated_at,
    }


def outbound_email_to_model(outbound: OutboundEmail) -> OutboundEmailOut:
    return OutboundEmailOut.model_validate(outbound_email_to_api(outbound))


def sequence_enrollment_to_api(enrollment: SequenceEnrollment) -> dict[str, object]:
    return {
        "id": enrollment.id,
        "sequence_id": enrollment.sequence_id,
        "crm_target_id": enrollment.crm_target_id,
        "contact_id": enrollment.contact_id,
        "account_id": enrollment.account_id,
        "status": enrollment.status,
        "approval_actor": enrollment.approval_actor,
        "approval_reason": enrollment.approval_reason,
        "current_step_order": enrollment.current_step_order,
        "definition_version": enrollment.definition_version,
        "next_step_at": enrollment.next_step_at,
        "pause_reason": enrollment.pause_reason,
        "policy_snapshot": enrollment.policy_snapshot or {},
        "version": enrollment.version,
        "created_at": enrollment.created_at,
        "updated_at": enrollment.updated_at,
        "completed_at": enrollment.completed_at,
    }


def sequence_enrollment_to_model(
    enrollment: SequenceEnrollment,
    outbound_emails: list[OutboundEmail] | None = None,
    display: dict[str, object] | None = None,
) -> SequenceEnrollmentOut:
    payload = sequence_enrollment_to_api(enrollment)
    payload.update(display or {})
    payload["outbound_emails"] = [
        outbound_email_to_api(outbound) for outbound in outbound_emails or []
    ]
    return SequenceEnrollmentOut.model_validate(payload)


def sequence_email_alert_to_api(alert: SequenceEmailAlert) -> dict[str, object]:
    return {
        "id": alert.id,
        "enrollment_id": alert.enrollment_id,
        "recipient_email": alert.recipient_email,
        "subject": alert.subject,
        "body": alert.body,
        "send_at": alert.send_at,
        "status": alert.status,
        "actor": alert.actor,
        "provider_message_id": alert.provider_message_id,
        "last_error": alert.last_error,
        "sent_at": alert.sent_at,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


def sequence_email_alert_to_model(alert: SequenceEmailAlert) -> SequenceEmailAlertOut:
    return SequenceEmailAlertOut.model_validate(sequence_email_alert_to_api(alert))


def sequence_activity_to_api(activity: SequenceStepActivity) -> dict[str, object]:
    return {
        "id": activity.id,
        "enrollment_id": activity.enrollment_id,
        "sequence_step_id": activity.sequence_step_id,
        "outbound_email_id": activity.outbound_email_id,
        "meeting_handoff_id": activity.meeting_handoff_id,
        "step_order": activity.step_order,
        "channel": activity.channel,
        "status": activity.status,
        "due_at": activity.due_at,
        "approved_by": activity.approved_by,
        "approved_at": activity.approved_at,
        "completed_by": activity.completed_by,
        "completed_at": activity.completed_at,
        "metadata": activity.metadata_payload or {},
        "created_at": activity.created_at,
        "updated_at": activity.updated_at,
    }


async def _activity_to_model_with_display(
    session: Any,
    activity: SequenceStepActivity,
) -> SequenceActivityOut:
    payload = sequence_activity_to_api(activity)
    enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
    sequence = await session.get(Sequence, enrollment.sequence_id) if enrollment else None
    contact = await session.get(Contact, enrollment.contact_id) if enrollment else None
    account = (
        await session.get(Account, enrollment.account_id)
        if enrollment and enrollment.account_id
        else None
    )
    payload.update(
        {
            "sequence_id": sequence.id if sequence else None,
            "sequence_name": sequence.name if sequence else None,
            "contact_name": contact.full_name if contact else None,
            "contact_email": contact.email if contact else None,
            "account_name": account.company_name if account else None,
        }
    )
    return SequenceActivityOut.model_validate(payload)


def inbound_event_to_api(event: InboundEmailEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "enrollment_id": event.enrollment_id,
        "outbound_email_id": event.outbound_email_id,
        "event_type": event.event_type,
        "from_email": event.from_email,
        "to_email": event.to_email,
        "message_id": event.message_id,
        "provider_payload": event.provider_payload or {},
        "occurred_at": event.occurred_at,
        "created_at": event.created_at,
    }


def inbound_event_to_model(event: InboundEmailEvent) -> InboundEmailEventOut:
    return InboundEmailEventOut.model_validate(inbound_event_to_api(event))


async def _sequence_steps(
    session: Any,
    sequence_id: str,
    definition_version: int | None = None,
) -> list[SequenceStep]:
    if definition_version is None:
        sequence = await session.get(Sequence, sequence_id)
        definition_version = sequence.definition_version if sequence else 1
    result = await session.execute(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .where(SequenceStep.definition_version == definition_version)
        .where(SequenceStep.active.is_(True))
        .order_by(SequenceStep.step_order)
    )
    return list(result.scalars())


def _requires_approval(channel: str, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return channel == "email"


async def _activity_for_step(
    session: Any,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    *,
    status: str,
    outbound_email_id: str | None = None,
) -> SequenceStepActivity:
    key = f"sequence_activity:{enrollment.id}:{step.id}"
    existing = await session.scalar(
        select(SequenceStepActivity).where(SequenceStepActivity.idempotency_key == key)
    )
    if existing is not None:
        if outbound_email_id and not existing.outbound_email_id:
            existing.outbound_email_id = outbound_email_id
        return existing
    now = utcnow()
    activity = SequenceStepActivity(
        enrollment_id=enrollment.id,
        sequence_step_id=step.id,
        outbound_email_id=outbound_email_id,
        meeting_handoff_id=None,
        step_order=step.step_order,
        channel=step.channel,
        status=status,
        due_at=now,
        approved_by=None,
        approved_at=None,
        completed_by=None,
        completed_at=None,
        metadata_payload=dict(step.step_metadata or {}),
        idempotency_key=key,
        created_at=now,
        updated_at=now,
    )
    session.add(activity)
    await session.flush()
    return activity


async def _enrollment_to_model_with_emails(
    session: Any,
    enrollment: SequenceEnrollment,
) -> SequenceEnrollmentOut:
    email_result = await session.execute(
        select(OutboundEmail)
        .where(OutboundEmail.enrollment_id == enrollment.id)
        .order_by(OutboundEmail.created_at)
    )
    sequence = await session.get(Sequence, enrollment.sequence_id)
    contact = await session.get(Contact, enrollment.contact_id)
    account = await session.get(Account, enrollment.account_id) if enrollment.account_id else None
    target = await session.get(CrmTarget, enrollment.crm_target_id)
    display = {
        "sequence_name": sequence.name if sequence else None,
        "contact_name": contact.full_name if contact else None,
        "contact_email": contact.email if contact else None,
        "account_name": account.company_name if account else None,
        "account_domain": account.domain if account else None,
        "crm_target_summary": _crm_target_summary(target),
    }
    return sequence_enrollment_to_model(enrollment, list(email_result.scalars()), display)


async def _set_enrollment_status(
    enrollment_id: str,
    *,
    status: str,
    reason: str,
    event_name: EventName | None,
    settings: Settings | None,
) -> SequenceEnrollmentOut | None:
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        if enrollment.status in TERMINAL_ENROLLMENT_STATUSES and status != enrollment.status:
            raise ValueError(f"cannot change {enrollment.status} enrollment")
        enrollment.status = status
        enrollment.pause_reason = reason
        enrollment.version += 1
        enrollment.updated_at = utcnow()
        if status in TERMINAL_ENROLLMENT_STATUSES:
            enrollment.completed_at = utcnow()
        if event_name is not None:
            _enqueue_event(
                session,
                event_name,
                "sequence_enrollment",
                enrollment.id,
                sequence_enrollment_to_api(enrollment),
                f"{event_name.value}:{enrollment.id}:{enrollment.version}",
            )
        return await _enrollment_to_model_with_emails(session, enrollment)


async def _contact_for_target(
    session: Any,
    target: CrmTarget,
    requested_contact_id: str | None,
) -> Contact:
    if requested_contact_id:
        contact = await session.get(Contact, requested_contact_id)
        if contact is None:
            raise ValueError("contact not found")
        return contact
    if target.target_type in {"contact", "incident_contact"}:
        contact = await session.get(Contact, target.target_id)
        if contact is not None:
            return contact
    if target.target_type == "email_candidate":
        candidate = await session.get(EmailCandidateRecord, target.target_id)
        if candidate is not None and candidate.contact_id:
            contact = await session.get(Contact, candidate.contact_id)
            if contact is not None:
                return contact
    raise ValueError("sequence enrollment requires a contact")


def _require_sendable_contact(contact: Contact) -> None:
    if contact.do_not_contact_flag:
        raise ValueError("contact is marked do-not-contact")
    if not contact.email:
        raise ValueError("contact has no email")
    if contact.email_status != "verified":
        raise ValueError("contact email must be verified before outreach")
    if not contact.lawful_basis:
        raise ValueError("contact is missing lawful basis")


async def _suppression_allowed(
    session: Any,
    *,
    email: str | None,
    domain: str | None,
    contact_id: str | None,
    channel: str,
) -> Any:
    baseline = evaluate_suppression(
        SuppressionCheckRequest(
            email=email,
            domain=domain,
            contact_id=contact_id,
            channel=channel,
        )
    )
    if not baseline.allowed:
        return baseline
    matches = []
    if email:
        matches.append(Suppression.email == email.lower())
    if domain:
        matches.append(Suppression.domain == domain.lower())
    if contact_id:
        matches.append(Suppression.contact_id == contact_id)
    if not matches:
        return baseline
    suppression = await session.scalar(
        select(Suppression)
        .where(Suppression.active.is_(True))
        .where(Suppression.channel == channel.lower())
        .where(or_(Suppression.expires_at.is_(None), Suppression.expires_at > utcnow()))
        .where(or_(*matches))
        .limit(1)
    )
    if suppression is None:
        return baseline
    return baseline.model_copy(update={"allowed": False, "reason": suppression.reason})


async def _step_for_order(
    session: Any,
    sequence_id: str,
    step_order: int,
    definition_version: int | None = None,
) -> SequenceStep | None:
    query = (
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .where(SequenceStep.step_order == step_order)
        .where(SequenceStep.active.is_(True))
    )
    if definition_version is not None:
        query = query.where(SequenceStep.definition_version == definition_version)
    else:
        query = query.order_by(SequenceStep.definition_version.desc())
    return await session.scalar(query.limit(1))


async def _outbound_for_step(
    session: Any,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    contact: Contact,
    account: Account | None,
    from_email: str,
) -> OutboundEmail:
    key = f"sequence_email:{enrollment.id}:{step.id}"
    existing = await session.scalar(
        select(OutboundEmail).where(OutboundEmail.idempotency_key == key)
    )
    if existing is not None:
        return existing
    now = utcnow()
    outbound = OutboundEmail(
        enrollment_id=enrollment.id,
        sequence_step_id=step.id,
        contact_id=contact.id,
        channel=step.channel,
        to_email=contact.email.lower(),
        from_email=from_email,
        subject=_render_template(step.subject_template or "", contact, account),
        body=_render_template(step.body_template or "", contact, account),
        status="pending",
        idempotency_key=key,
        attempt_count=0,
        scheduled_at=enrollment.next_step_at or now,
        created_at=now,
        updated_at=now,
    )
    session.add(outbound)
    await session.flush()
    return outbound


async def _advance_enrollment(
    session: Any,
    enrollment: SequenceEnrollment,
    current_step: SequenceStep,
) -> None:
    steps = await _sequence_steps(
        session,
        enrollment.sequence_id,
        enrollment.definition_version,
    )
    next_steps = [step for step in steps if step.step_order > current_step.step_order]
    now = utcnow()
    if not next_steps:
        _complete_enrollment(session, enrollment)
        return
    next_step = next_steps[0]
    enrollment.current_step_order = next_step.step_order
    enrollment.next_step_at = now + timedelta(seconds=next_step.delay_seconds)
    enrollment.version += 1
    enrollment.updated_at = now


def _complete_enrollment(session: Any, enrollment: SequenceEnrollment) -> None:
    enrollment.status = "completed"
    enrollment.next_step_at = None
    enrollment.pause_reason = None
    enrollment.completed_at = utcnow()
    enrollment.version += 1
    enrollment.updated_at = utcnow()
    _enqueue_event(
        session,
        EventName.SEQUENCE_COMPLETED,
        "sequence_enrollment",
        enrollment.id,
        sequence_enrollment_to_api(enrollment),
        f"sequence.completed:{enrollment.id}:{enrollment.version}",
    )


async def _pause_for_policy(
    session: Any,
    enrollment: SequenceEnrollment,
    reason: str,
) -> None:
    enrollment.status = "paused"
    enrollment.pause_reason = reason
    enrollment.version += 1
    enrollment.updated_at = utcnow()
    _enqueue_event(
        session,
        EventName.SEQUENCE_PAUSED,
        "sequence_enrollment",
        enrollment.id,
        sequence_enrollment_to_api(enrollment),
        f"sequence.paused:{enrollment.id}:{enrollment.version}",
    )


async def _suppress_enrollment(
    session: Any,
    enrollment: SequenceEnrollment,
    contact: Contact,
    reason: str | None,
) -> None:
    enrollment.status = "suppressed"
    enrollment.pause_reason = reason or "suppression blocks outreach"
    enrollment.completed_at = utcnow()
    enrollment.version += 1
    enrollment.updated_at = utcnow()
    session.add(
        SequenceSuppressionEvent(
            enrollment_id=enrollment.id,
            email=contact.email.lower() if contact.email else None,
            domain=_domain_from_email(contact.email),
            channel="email",
            reason=enrollment.pause_reason,
        )
    )
    _enqueue_event(
        session,
        EventName.SEQUENCE_PAUSED,
        "sequence_enrollment",
        enrollment.id,
        sequence_enrollment_to_api(enrollment),
        f"sequence.paused:{enrollment.id}:{enrollment.version}",
    )


async def _rate_limit_blocker(
    session: Any,
    *,
    to_email: str,
    from_email: str,
    channel: str,
    sequence: Sequence,
    settings: Settings,
) -> str | None:
    policy = sequence.rate_limit_policy or {}
    domain_limit = int(policy.get("domain_daily_limit") or settings.sequence_domain_daily_limit)
    sender_limit = int(policy.get("sender_daily_limit") or settings.sequence_sender_daily_limit)
    channel_limit = int(policy.get("channel_daily_limit") or settings.sequence_channel_daily_limit)
    domain = _domain_from_email(to_email)
    since = utcnow() - timedelta(days=1)
    result = await session.execute(
        select(OutboundEmail)
        .where(OutboundEmail.status == "sent")
        .where(OutboundEmail.channel == channel)
        .where(OutboundEmail.sent_at >= since)
    )
    sent = list(result.scalars())
    domain_count = len([email for email in sent if _domain_from_email(email.to_email) == domain])
    sender_count = len([email for email in sent if email.from_email.lower() == from_email.lower()])
    channel_count = len(sent)
    if domain_count >= domain_limit:
        return f"domain daily rate limit reached for {domain}"
    if sender_count >= sender_limit:
        return f"sender daily rate limit reached for {from_email}"
    if channel_count >= channel_limit:
        return f"channel daily rate limit reached for {channel}"
    return None


async def _find_outbound_for_inbound(
    session: Any,
    request: InboundEmailEventCreate,
) -> OutboundEmail | None:
    if request.provider_message_id:
        outbound = await session.scalar(
            select(OutboundEmail)
            .where(OutboundEmail.provider_message_id == request.provider_message_id)
            .order_by(OutboundEmail.sent_at.desc())
            .limit(1)
        )
        if outbound is not None:
            return outbound
    email = str(request.from_email or "").lower()
    if not email:
        return None
    return await session.scalar(
        select(OutboundEmail)
        .where(OutboundEmail.to_email == email)
        .where(OutboundEmail.status == "sent")
        .order_by(OutboundEmail.sent_at.desc())
        .limit(1)
    )


async def _find_enrollment_by_email(
    session: Any,
    email: str | None,
) -> SequenceEnrollment | None:
    if not email:
        return None
    outbound = await session.scalar(
        select(OutboundEmail)
        .where(OutboundEmail.to_email == str(email).lower())
        .order_by(OutboundEmail.created_at.desc())
        .limit(1)
    )
    return await session.get(SequenceEnrollment, outbound.enrollment_id) if outbound else None


async def _create_unsubscribe_suppression(
    session: Any,
    *,
    email: str,
    channel: str,
    reason: str,
    source_event: InboundEmailEvent,
    enrollment: SequenceEnrollment | None,
) -> None:
    domain = _domain_from_email(email)
    suppression = await session.scalar(
        select(Suppression)
        .where(Suppression.email == email.lower())
        .where(Suppression.channel == channel.lower())
        .where(Suppression.active.is_(True))
        .limit(1)
    )
    if suppression is None:
        suppression = Suppression(
            email=email.lower(),
            domain=domain,
            channel=channel.lower(),
            reason=reason,
            source="unsubscribe",
            active=True,
            policy_snapshot={"source_event_id": source_event.id},
            idempotency_key=f"unsubscribe:{channel.lower()}:{email.lower()}",
        )
        session.add(suppression)
        await session.flush()
        _enqueue_event(
            session,
            EventName.SUPPRESSION_CREATED,
            "suppression",
            suppression.id,
            {
                "id": suppression.id,
                "email": suppression.email,
                "domain": suppression.domain,
                "channel": suppression.channel,
                "reason": suppression.reason,
                "source": suppression.source,
            },
            f"suppression.created:{suppression.id}",
        )
    session.add(
        SequenceSuppressionEvent(
            enrollment_id=enrollment.id if enrollment else None,
            suppression_id=suppression.id,
            email=email.lower(),
            domain=domain,
            channel=channel.lower(),
            reason=reason,
            source_event_id=source_event.id,
        )
    )


def _enqueue_event(
    session: Any,
    event_name: EventName,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, object],
    idempotency_key: str,
) -> OutboxEvent:
    event = new_event(
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        source_service=SEQUENCING_SERVICE_NAME,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    outbox = OutboxEvent(
        event_name=event.event_name,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        idempotency_key=event.idempotency_key,
        payload=event.model_dump(mode="json"),
    )
    session.add(outbox)
    return outbox


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


def utcnow() -> datetime:
    return datetime.now(UTC)


class _SafeFormat(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""
