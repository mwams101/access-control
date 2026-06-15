"""Core workflows: approval, pass issuance, verification, check-in/out.

All state changes go through these functions so that audit logging (FR-23)
and notifications (FR-19/20/21) are applied consistently.
"""
from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.access.models import blacklist_hit
from apps.notifications import services as notify
from apps.reports.services import log_action

from .models import CheckInEvent, Pass, VisitRequest
from .utils import make_pass_token, read_pass_token


# ---------------------------------------------------------------------------
# Approval workflow (FR-07, FR-08)
# ---------------------------------------------------------------------------

@transaction.atomic
def approve_visit(visit: VisitRequest, actor, zones=None, single_entry=True) -> Pass:
    if visit.status != VisitRequest.Status.PENDING:
        raise ValueError(f"Cannot approve a visit in status {visit.status}.")

    visit.status = VisitRequest.Status.APPROVED
    visit.decided_by = actor
    visit.save(update_fields=["status", "decided_by"])

    padding = timezone.timedelta(
        minutes=settings.ACCESS_CONTROL["PASS_WINDOW_PADDING_MINUTES"]
    )
    access_pass = Pass.objects.create(
        visit=visit,
        token="pending",
        valid_from=visit.expected_start - padding,
        valid_until=visit.expected_end + padding,
        single_entry=single_entry,
    )
    access_pass.token = make_pass_token(access_pass.pk)
    access_pass.save(update_fields=["token"])
    if zones:
        access_pass.zones.set(zones)

    log_action(actor, "visit.approved", visit)
    notify.visit_approved(visit, access_pass)
    return access_pass


@transaction.atomic
def deny_visit(visit: VisitRequest, actor, reason: str = ""):
    if visit.status != VisitRequest.Status.PENDING:
        raise ValueError(f"Cannot deny a visit in status {visit.status}.")
    visit.status = VisitRequest.Status.DENIED
    visit.decided_by = actor
    visit.decision_note = reason[:255]
    visit.save(update_fields=["status", "decided_by", "decision_note"])
    log_action(actor, "visit.denied", visit, metadata={"reason": reason})
    notify.visit_denied(visit, reason)


@transaction.atomic
def cancel_visit(visit: VisitRequest, actor):
    if visit.status not in (VisitRequest.Status.PENDING, VisitRequest.Status.APPROVED):
        raise ValueError("Only pending or approved visits can be cancelled.")
    visit.status = VisitRequest.Status.CANCELLED
    visit.save(update_fields=["status"])
    if hasattr(visit, "access_pass"):
        visit.access_pass.revoked = True
        visit.access_pass.save(update_fields=["revoked"])
    log_action(actor, "visit.cancelled", visit)


# ---------------------------------------------------------------------------
# Pass verification (FR-11, FR-12 — Section 7.3 of the design doc)
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    allowed: bool
    reason: str = ""
    access_pass: Pass | None = None
    alert: bool = False  # blacklist hits raise an admin alert (FR-21)


def verify_pass(token: str, actor=None, gate: str = "Main Gate") -> VerificationResult:
    try:
        pass_id = read_pass_token(token)
        access_pass = Pass.objects.select_related("visit").get(pk=pass_id)
    except (signing.BadSignature, KeyError, ValueError, Pass.DoesNotExist):
        return VerificationResult(False, "Invalid or tampered pass token.")

    return _evaluate_pass(access_pass, actor=actor, gate=gate)


def verify_by_reference(reference: str, actor=None, gate: str = "Main Gate") -> VerificationResult:
    """Fallback lookup when there is no QR to scan (FR-11)."""
    try:
        access_pass = Pass.objects.select_related("visit").get(
            visit__reference__iexact=reference.strip()
        )
    except Pass.DoesNotExist:
        return VerificationResult(False, "No pass found for that reference.")
    return _evaluate_pass(access_pass, actor=actor, gate=gate)


def _evaluate_pass(access_pass: Pass, actor=None, gate: str = "Main Gate") -> VerificationResult:
    visit = access_pass.visit
    now = timezone.now()

    def deny(reason: str, alert: bool = False) -> VerificationResult:
        if actor is not None:
            CheckInEvent.objects.create(
                pass_obj=access_pass, kind=CheckInEvent.Kind.DENIED,
                gate=gate, performed_by=actor, note=reason[:255],
            )
            log_action(actor, "pass.denied", visit, metadata={"reason": reason})
            if alert:
                notify.security_alert(
                    f"Blacklisted visitor attempted entry: {visit.display_name} "
                    f"({visit.reference}) at {gate}."
                )
        return VerificationResult(False, reason, access_pass, alert)

    if access_pass.revoked:
        return deny("Pass has been revoked.")
    if visit.status in (VisitRequest.Status.DENIED, VisitRequest.Status.CANCELLED):
        return deny(f"Visit is {visit.get_status_display().lower()}.")
    if not (access_pass.valid_from <= now <= access_pass.valid_until):
        return deny("Pass is outside its valid time window.")
    if access_pass.single_entry and access_pass.has_entered:
        return deny("Single-entry pass has already been used.")

    hit = blacklist_hit(visit.full_name, visit.id_number)
    if hit:
        return deny("Visitor is blacklisted.", alert=True)

    return VerificationResult(True, "Pass is valid.", access_pass)


# ---------------------------------------------------------------------------
# Check-in / check-out (FR-13, FR-14)
# ---------------------------------------------------------------------------

@transaction.atomic
def check_in(access_pass: Pass, actor, gate: str = "Main Gate", photo=None, note=""):
    result = _evaluate_pass(access_pass, actor=None)  # re-validate without logging a DENIED
    if not result.allowed:
        raise ValueError(result.reason)

    event = CheckInEvent.objects.create(
        pass_obj=access_pass, kind=CheckInEvent.Kind.IN,
        gate=gate, performed_by=actor, photo=photo, note=note,
    )
    visit = access_pass.visit
    visit.status = VisitRequest.Status.CHECKED_IN
    visit.save(update_fields=["status"])

    log_action(actor, "pass.checked_in", visit, metadata={"gate": gate})
    notify.host_visitor_arrived(visit)
    return event


@transaction.atomic
def check_out(access_pass: Pass, actor, gate: str = "Main Gate", note=""):
    visit = access_pass.visit
    if visit.status != VisitRequest.Status.CHECKED_IN:
        raise ValueError("Visitor is not currently checked in.")

    event = CheckInEvent.objects.create(
        pass_obj=access_pass, kind=CheckInEvent.Kind.OUT,
        gate=gate, performed_by=actor, note=note,
    )
    visit.status = VisitRequest.Status.CHECKED_OUT
    visit.save(update_fields=["status"])
    log_action(actor, "pass.checked_out", visit, metadata={"gate": gate})
    return event


# ---------------------------------------------------------------------------
# Walk-in registration (FR-09 — Section 7.2 of the design doc)
# ---------------------------------------------------------------------------

@transaction.atomic
def register_walk_in(visit: VisitRequest, actor, gate: str = "Main Gate",
                     zones=None) -> VerificationResult:
    """Blacklist-check, auto-approve, issue pass, and check in — one step."""
    hit = blacklist_hit(visit.full_name, visit.id_number)
    if hit:
        visit.status = VisitRequest.Status.DENIED
        visit.decided_by = actor
        visit.decision_note = "Blacklist match at walk-in registration."
        visit.save()
        log_action(actor, "walkin.blacklist_hit", visit, metadata={"reason": hit.reason})
        notify.security_alert(
            f"Blacklisted walk-in attempt: {visit.display_name} at {gate}."
        )
        return VerificationResult(False, "Visitor is blacklisted.", alert=True)

    access_pass = approve_visit(visit, actor, zones=zones, single_entry=True)
    check_in(access_pass, actor, gate=gate)
    log_action(actor, "walkin.registered", visit, metadata={"gate": gate})
    return VerificationResult(True, "Walk-in checked in.", access_pass)


# ---------------------------------------------------------------------------
# Occupancy & housekeeping (FR-15, lifecycle EXPIRED)
# ---------------------------------------------------------------------------

def currently_inside():
    return (
        VisitRequest.objects.filter(status=VisitRequest.Status.CHECKED_IN)
        .select_related("host")
        .order_by("expected_end")
    )


def expire_stale_requests():
    """Mark approved-but-never-used visits as EXPIRED. Run periodically
    (cron / Celery beat): `python manage.py expire_visits`."""
    now = timezone.now()
    return VisitRequest.objects.filter(
        status__in=[VisitRequest.Status.PENDING, VisitRequest.Status.APPROVED],
        expected_end__lt=now - timezone.timedelta(hours=1),
    ).update(status=VisitRequest.Status.EXPIRED)
