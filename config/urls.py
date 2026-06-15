from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="accounts:post_login"), name="home"),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("visits/", include("apps.visits.urls", namespace="visits")),
    path("access/", include("apps.access.urls", namespace="access")),
    path("reports/", include("apps.reports.urls", namespace="reports")),
    path("api/v1/", include("config.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
