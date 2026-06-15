from django.urls import path

from . import views

app_name = "visits"

urlpatterns = [
    # Visitor
    path("mine/", views.MyVisitsView.as_view(), name="my_visits"),
    path("new/", views.VisitCreateView.as_view(), name="visit_create"),
    path("<int:pk>/", views.VisitDetailView.as_view(), name="visit_detail"),
    # Security / gate
    path("gate/", views.GateDashboardView.as_view(), name="gate_dashboard"),
    path("gate/verify/", views.VerifyPassView.as_view(), name="verify"),
    path("gate/pass/<int:pk>/<str:action>/", views.CheckInActionView.as_view(), name="pass_action"),
    path("gate/walkin/", views.WalkInCreateView.as_view(), name="walkin"),
    path("gate/pending/", views.PendingApprovalsView.as_view(), name="pending"),
    path("gate/decide/<int:pk>/", views.DecideVisitView.as_view(), name="decide"),
    path("gate/occupancy/", views.OccupancyView.as_view(), name="occupancy"),
]
