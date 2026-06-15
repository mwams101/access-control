import csv

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.accounts.mixins import AdminRequiredMixin
from apps.visits.models import CheckInEvent, VisitRequest
from apps.visits.services import currently_inside

from .models import AuditLog
from .services import log_action


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """FR-22 — admin overview."""

    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        ctx["visitors_today"] = CheckInEvent.objects.filter(
            kind=CheckInEvent.Kind.IN, timestamp__date=today
        ).count()
        ctx["inside"] = currently_inside()
        ctx["pending_count"] = VisitRequest.objects.filter(
            status=VisitRequest.Status.PENDING
        ).count()
        ctx["denied_today"] = CheckInEvent.objects.filter(
            kind=CheckInEvent.Kind.DENIED, timestamp__date=today
        ).count()
        ctx["overdue"] = [v for v in ctx["inside"] if v.is_overdue]

        since = timezone.now() - timezone.timedelta(days=30)
        ctx["traffic"] = (
            CheckInEvent.objects.filter(kind=CheckInEvent.Kind.IN, timestamp__gte=since)
            .annotate(day=TruncDate("timestamp"))
            .values("day").annotate(total=Count("id")).order_by("day")
        )
        return ctx


class VisitsReportView(AdminRequiredMixin, ListView):
    """FR-24 — filterable report with CSV export at ?format=csv."""

    template_name = "reports/visits_report.html"
    context_object_name = "visits"
    paginate_by = 50

    def get_queryset(self):
        qs = VisitRequest.objects.select_related("host").order_by("-expected_start")
        params = self.request.GET
        if params.get("from"):
            qs = qs.filter(expected_start__date__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(expected_start__date__lte=params["to"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("host"):
            qs = qs.filter(host_id=params["host"])
        return qs

    def render_to_response(self, context, **kwargs):
        if self.request.GET.get("format") == "csv":
            return self._csv(self.get_queryset())
        return super().render_to_response(context, **kwargs)

    def _csv(self, queryset):
        log_action(self.request.user, "report.exported", metadata={"filters": dict(self.request.GET)})
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="visits_report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Reference", "Name", "Entity", "Host", "Status",
                         "Expected start", "Expected end", "Created"])
        for v in queryset:
            writer.writerow([
                v.reference, v.full_name, v.entity_name,
                v.host.get_full_name() or v.host.username, v.status,
                v.expected_start.isoformat(), v.expected_end.isoformat(),
                v.created_at.isoformat(),
            ])
        return response


class AuditLogListView(AdminRequiredMixin, ListView):
    template_name = "reports/audit_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor")
        action = self.request.GET.get("action")
        return qs.filter(action=action) if action else qs


class AuditLogExportView(AdminRequiredMixin, View):
    def get(self, request):
        log_action(request.user, "audit.exported")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit_log.csv"'
        writer = csv.writer(response)
        writer.writerow(["Timestamp", "Actor", "Action", "Target type", "Target id", "Metadata"])
        for e in AuditLog.objects.select_related("actor").iterator():
            writer.writerow([
                e.timestamp.isoformat(), getattr(e.actor, "username", ""),
                e.action, e.target_type, e.target_id, e.metadata,
            ])
        return response
