from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from .health import live, ready
from .media import debug_media_serve

urlpatterns = [
    path("healthz", live, name="healthz"),
    path("readyz", ready, name="readyz"),
    path("django-admin/", admin.site.urls),
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
