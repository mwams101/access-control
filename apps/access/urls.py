from django.urls import path

from . import views

app_name = "access"

urlpatterns = [
    path("zones/", views.ZoneListView.as_view(), name="zones"),
    path("zones/new/", views.ZoneCreateView.as_view(), name="zone_create"),
    path("zones/<int:pk>/edit/", views.ZoneUpdateView.as_view(), name="zone_edit"),
    path("blacklist/", views.BlacklistListView.as_view(), name="blacklist"),
    path("blacklist/new/", views.BlacklistCreateView.as_view(), name="blacklist_create"),
    path("blacklist/<int:pk>/edit/", views.BlacklistUpdateView.as_view(), name="blacklist_edit"),
]
