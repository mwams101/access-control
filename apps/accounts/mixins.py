"""Role-based access mixins for class-based views (FR-03)."""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Deny access unless request.user.role is in `allowed_roles`."""

    allowed_roles: tuple = ()
    raise_exception = True  # 403 instead of redirect loop for logged-in users

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return user.role in self.allowed_roles


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ("ADMIN",)


class SecurityRequiredMixin(RoleRequiredMixin):
    """Security or Admin (admins can do everything security can)."""

    allowed_roles = ("SECURITY", "ADMIN")


class VisitorRequiredMixin(RoleRequiredMixin):
    allowed_roles = ("VISITOR",)
