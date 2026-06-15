"""DRF permission classes (Section 8 of the design doc)."""
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and (u.role == "ADMIN" or u.is_superuser)


class IsSecurity(BasePermission):
    """Security or Admin."""

    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and (u.role in ("SECURITY", "ADMIN") or u.is_superuser)


class IsOwnerVisitor(BasePermission):
    """Visitors may only access their own objects."""

    def has_object_permission(self, request, view, obj):
        u = request.user
        if u.role in ("SECURITY", "ADMIN") or u.is_superuser:
            return True
        visitor_id = getattr(obj, "visitor_id", None)
        return visitor_id == u.id
