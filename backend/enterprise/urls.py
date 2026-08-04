from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContentPublishView, CurrentContextView, DuplicatePatientScanView, EnterpriseMetricsView,
    EnterpriseReadinessView, EnterpriseRecordViewSet, EnterpriseSummaryView, EventDeliveryActionView,
    EventReplayActionView, ImagingViewerConfigView, MedicationSafetyCheckView, NearestAmbulanceView,
    NotificationProviderHealthView, PACSHealthView, PartnerTokenView, PatientFHIRExportView,
    PatientMergeActionView, PublicContentView, RESOURCE_VIEWSETS, ReportRunActionView,
    RoleContextViewSet, RoleDelegationViewSet, SchemaCatalogView, TelemedicineActionView, VerificationRunView, EnterpriseEntityLookupView, RoleDashboardView,
)

router = DefaultRouter()
router.register("contexts", RoleContextViewSet, basename="enterprise-context")
router.register("delegations", RoleDelegationViewSet, basename="enterprise-delegation")
router.register("records", EnterpriseRecordViewSet, basename="enterprise-record")
for route, viewset in RESOURCE_VIEWSETS.items():
    router.register(route, viewset, basename=f"enterprise-{route}")

urlpatterns = [
    path("", include(router.urls)),
    path("schema/", SchemaCatalogView.as_view(), name="enterprise-schema"),
    path("summary/", EnterpriseSummaryView.as_view(), name="enterprise-summary"),
    path("dashboard/role/", RoleDashboardView.as_view(), name="enterprise-role-dashboard"),
    path("lookups/", EnterpriseEntityLookupView.as_view(), name="enterprise-entity-lookups"),
    path("context/current/", CurrentContextView.as_view(), name="enterprise-current-context"),
    path("public/content/", PublicContentView.as_view(), name="enterprise-public-content"),
    path("content/<int:pk>/publish/", ContentPublishView.as_view(), name="enterprise-content-publish"),
    path("patient-merges/<int:pk>/action/", PatientMergeActionView.as_view(), name="enterprise-patient-merge-action"),
    path("telemedicine-sessions/<int:pk>/action/", TelemedicineActionView.as_view(), name="enterprise-telemedicine-action"),
    path("event-deliveries/<int:pk>/action/", EventDeliveryActionView.as_view(), name="enterprise-event-delivery-action"),
    path("verification-automation/<int:pk>/action/", VerificationRunView.as_view(), name="enterprise-verification-action"),
    path("saved-reports/<int:pk>/run/", ReportRunActionView.as_view(), name="enterprise-report-run"),
    path("partner-apps/<int:pk>/token/", PartnerTokenView.as_view(), name="enterprise-partner-token"),
    path("clinical/medication-safety/", MedicationSafetyCheckView.as_view(), name="enterprise-medication-safety"),
    path("pacs-nodes/<int:pk>/health/", PACSHealthView.as_view(), name="enterprise-pacs-health"),
    path("imaging-studies/<int:pk>/viewer/", ImagingViewerConfigView.as_view(), name="enterprise-imaging-viewer"),
    path("ambulances/nearest/", NearestAmbulanceView.as_view(), name="enterprise-nearest-ambulance"),
    path("records/duplicate-scan/", DuplicatePatientScanView.as_view(), name="enterprise-duplicate-scan"),
    path("notification-providers/<int:pk>/health/", NotificationProviderHealthView.as_view(), name="enterprise-provider-health"),
    path("fhir/export/me/", PatientFHIRExportView.as_view(), name="enterprise-fhir-export-me"),
    path("fhir/export/patients/<int:patient_id>/", PatientFHIRExportView.as_view(), name="enterprise-fhir-export-patient"),
    path("replay-requests/<int:pk>/run/", EventReplayActionView.as_view(), name="enterprise-replay-run"),
    path("metrics/", EnterpriseMetricsView.as_view(), name="enterprise-metrics"),
    path("readiness/", EnterpriseReadinessView.as_view(), name="enterprise-readiness"),
]
