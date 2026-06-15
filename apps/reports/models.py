from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only record of every state-changing action (FR-23 / NFR-06).

    No update or delete views exist for this model anywhere in the app.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=60, db_index=True)  # e.g. "visit.approved"
    target_type = models.CharField(max_length=60)
    target_id = models.CharField(max_length=40)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action} {self.target_type}#{self.target_id}"
