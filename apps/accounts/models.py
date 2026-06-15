from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Single user model covering all three roles (RBAC via `role`)."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        SECURITY = "SECURITY", "Security"
        VISITOR = "VISITOR", "Visitor"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VISITOR)
    phone = models.CharField(max_length=20, blank=True)
    # Required profile photo. blank=False makes it mandatory in every ModelForm
    # (visitor sign-up, admin user-add). At the DB level a FileField stores an
    # empty string rather than NULL, so CLI-created users (createsuperuser,
    # create_user) won't crash — see README for enforcing it for them too.
    image = models.ImageField(upload_to="user_photos/", blank=True, null=True)

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_security_role(self) -> bool:
        return self.role == self.Role.SECURITY

    @property
    def is_staff_role(self) -> bool:
        """Admin or Security — anyone who operates the system."""
        return self.is_admin_role or self.is_security_role

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"
