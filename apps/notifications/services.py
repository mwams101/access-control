"""Email notifications (FR-19/20/21).

These are deliberately plain functions so the system works without a task
queue. To move them off the request cycle later, wrap each in a Celery task
and call `.delay()` from the service layer — no other code changes needed.

In development the console email backend prints messages to the runserver
terminal. SMS (e.g. Africa's Talking) is a v2 integration point.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send(subject: str, body: str, recipients: list[str]):
    recipients = [r for r in recipients if r]
    if not recipients:
        return
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients,
                  fail_silently=True)
    except Exception:  # never let notifications break a workflow
        logger.exception("Failed to send notification email")


def visit_approved(visit, access_pass):
    _send(
        f"[Access Control] Visit {visit.reference} approved",
        (
            f"Hello {visit.full_name},\n\n"
            f"Your visit on {visit.expected_start:%d %b %Y %H:%M} has been approved.\n"
            f"Reference: {visit.reference}\n"
            f"Your pass is valid from {access_pass.valid_from:%H:%M} "
            f"to {access_pass.valid_until:%H:%M}.\n\n"
            f"Open your pass (QR code) here: /visits/{visit.pk}/\n"
            "Present the QR code or your reference at the gate."
        ),
        [visit.email],
    )


def visit_denied(visit, reason: str):
    _send(
        f"[Access Control] Visit {visit.reference} not approved",
        (
            f"Hello {visit.full_name},\n\n"
            f"Unfortunately your visit request {visit.reference} was not approved."
            + (f"\nReason: {reason}" if reason else "")
        ),
        [visit.email],
    )


def host_visitor_arrived(visit):
    """FR-19 — notify the host on visitor check-in."""
    _send(
        f"[Access Control] Your visitor has arrived ({visit.reference})",
        (
            f"Hello {visit.host.get_full_name() or visit.host.username},\n\n"
            f"{visit.display_name} has just checked in to see you.\n"
            f"Purpose: {visit.purpose}"
        ),
        [visit.host.email],
    )


def security_alert(message: str):
    """FR-21 — alert all active admins about a security event."""
    User = get_user_model()
    admin_emails = list(
        User.objects.filter(role="ADMIN", is_active=True).values_list("email", flat=True)
    )
    _send("[Access Control] SECURITY ALERT", message, admin_emails)
