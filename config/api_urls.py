"""REST API v1 — see Section 8 of the design document."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.visits import api as visits_api

router = DefaultRouter()
router.register("visits", visits_api.VisitRequestViewSet, basename="visit")

urlpatterns = [
    path("passes/verify/", visits_api.VerifyPassView.as_view(), name="api-pass-verify"),
    path("passes/<int:pk>/checkin/", visits_api.CheckInView.as_view(), name="api-pass-checkin"),
    path("passes/<int:pk>/checkout/", visits_api.CheckOutView.as_view(), name="api-pass-checkout"),
    path("occupancy/", visits_api.OccupancyView.as_view(), name="api-occupancy"),
]

urlpatterns += router.urls
