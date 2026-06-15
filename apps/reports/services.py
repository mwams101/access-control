"""Audit logging helper — call from every state-changing operation."""
from .models import AuditLog


def log_action(actor, action: str, target=None, metadata: dict | None = None):
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target.__class__.__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        metadata=metadata or {},
    )
