from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .health import live, ready
from .media import debug_media_serve

urlpatterns = [
    path("healthz", live, name="healthz"),
    path("readyz", ready, name="readyz"),
    path("django-admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
    path("api/", include("config.api_urls")),
    path("api/v1/", include("config.api_urls")),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            debug_media_serve,
            {"document_root": settings.MEDIA_ROOT},
            name="debug-media",
        )
    ]
