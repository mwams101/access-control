from django.conf import settings
from django.db import models


class Zone(models.Model):
    """A physical area of the building a pass can grant access to (FR-16)."""

    name = models.CharField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    restricted = models.BooleanField(
        default=False, help_text="Restricted zones require explicit admin approval."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Blacklist(models.Model):
    """Entries matched against visitors at check-in (FR-18)."""

    id_number = models.CharField(max_length=50, blank=True, db_index=True)
    full_name = models.CharField(max_length=120, blank=True, db_index=True)
    reason = models.TextField()
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Blacklist entries"
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name or self.id_number


def blacklist_hit(full_name: str, id_number: str):
    """Return the matching active Blacklist entry, or None."""
    qs = Blacklist.objects.filter(active=True)
    if id_number:
        match = qs.filter(id_number__iexact=id_number.strip()).first()
        if match:
            return match
    if full_name:
        match = qs.filter(full_name__iexact=full_name.strip()).exclude(full_name="").first()
        if match:
            return match
    return None
