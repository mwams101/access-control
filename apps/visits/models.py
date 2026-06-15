import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_reference() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "VR-" + "".join(secrets.choice(alphabet) for _ in range(6))


class VisitRequest(models.Model):
    """A request by an individual or entity to enter the building (FR-06/07/10)."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DENIED = "DENIED", "Denied"
        CHECKED_IN = "CHECKED_IN", "Checked in"
        CHECKED_OUT = "CHECKED_OUT", "Checked out"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    reference = models.CharField(max_length=12, unique=True, default=generate_reference)
    visitor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="visit_requests",
        help_text="Linked account; null for walk-ins registered by Security.",
    )
    full_name = models.CharField(max_length=120)
    id_type = models.CharField(max_length=30, default="NRC")
    id_number = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    is_entity = models.BooleanField(default=False, verbose_name="Entity / group visit")
    entity_name = models.CharField(max_length=120, blank=True)
    vehicle_reg = models.CharField(max_length=20, blank=True)

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="hosted_visits", on_delete=models.PROTECT
    )
    purpose = models.TextField()
    expected_start = models.DateTimeField()
    expected_end = models.DateTimeField()

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="+", on_delete=models.SET_NULL,
    )
    decision_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "expected_start"])]

    def __str__(self):
        who = self.entity_name if self.is_entity else self.full_name
        return f"{self.reference} — {who}"

    @property
    def display_name(self) -> str:
        return self.entity_name if self.is_entity and self.entity_name else self.full_name

    @property
    def masked_id(self) -> str:
        """PII minimization in list views (Section 9)."""
        visible = settings.ACCESS_CONTROL["ID_MASK_VISIBLE_CHARS"]
        if len(self.id_number) <= visible:
            return self.id_number
        return "****" + self.id_number[-visible:]

    @property
    def is_overdue(self) -> bool:
        """Checked in but past expected end + grace period (FR-14)."""
        if self.status != self.Status.CHECKED_IN:
            return False
        grace = settings.ACCESS_CONTROL["OVERDUE_GRACE_MINUTES"]
        return timezone.now() > self.expected_end + timezone.timedelta(minutes=grace)


class VisitorParty(models.Model):
    """Named individuals covered by an entity VisitRequest (FR-10)."""

    visit = models.ForeignKey(VisitRequest, related_name="party", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=120)
    id_number = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name_plural = "Visitor party members"

    def __str__(self):
        return self.full_name


class Pass(models.Model):
    """A time-bound, signed access pass issued on approval (FR-08)."""

    visit = models.OneToOneField(VisitRequest, on_delete=models.CASCADE, related_name="access_pass")
    token = models.CharField(max_length=255, unique=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    single_entry = models.BooleanField(default=True)
    zones = models.ManyToManyField("access.Zone", blank=True)
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Passes"

    def __str__(self):
        return f"Pass for {self.visit.reference}"

    @property
    def is_currently_valid(self) -> bool:
        now = timezone.now()
        return not self.revoked and self.valid_from <= now <= self.valid_until

    @property
    def has_entered(self) -> bool:
        return self.events.filter(kind=CheckInEvent.Kind.IN).exists()


class CheckInEvent(models.Model):
    """Every entry, exit, and denied attempt at a gate (FR-13/14)."""

    class Kind(models.TextChoices):
        IN = "IN", "Checked in"
        OUT = "OUT", "Checked out"
        DENIED = "DENIED", "Denied"

    pass_obj = models.ForeignKey(Pass, related_name="events", on_delete=models.PROTECT)
    kind = models.CharField(max_length=6, choices=Kind.choices)
    gate = models.CharField(max_length=60, default="Main Gate")
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    photo = models.ImageField(upload_to="checkin_photos/", blank=True)
    note = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.kind} {self.pass_obj.visit.reference} @ {self.gate}"
