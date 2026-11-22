"""MyDoctor public API route table.

Mounted at both ``/api/`` for backwards compatibility and ``/api/v1/`` for
explicitly versioned integrations.  New partner integrations should use v1.
"""

from django.urls import include, path

urlpatterns = [
    path("auth/", include("accounts.urls")),
    path("", include("accounts.api_urls")),
    path("", include("appointments.urls")),
    path("", include("communication.urls")),
    path("", include("payments.urls")),
    path("", include("prescriptions.urls")),
    path("services/", include("services.urls")),
    path("", include("reviews.urls")),
    path("admin/", include("dashboard.urls")),
    path("governance/", include("governance.urls")),
    path("clinical/", include("clinical.urls")),
    path("registry/", include("registry.urls")),
    path("interoperability/", include("interoperability.urls")),
    path("workforce/", include("workforce.urls")),
    path("operations/", include("operations.urls")),
]
