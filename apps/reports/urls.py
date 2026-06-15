from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("dashboard/", views.AdminDashboardView.as_view(), name="dashboard"),
    path("visits/", views.VisitsReportView.as_view(), name="visits_report"),
    path("audit/", views.AuditLogListView.as_view(), name="audit"),
    path("audit/export/", views.AuditLogExportView.as_view(), name="audit_export"),
]
