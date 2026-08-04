from django.urls import path

from .views import (
    CapabilityStatementView,
    OutboxEventListView,
    PatientSummaryExportView,
    TerminologyConceptManageView,
    TerminologySearchView,
)

urlpatterns = [
    path("fhir/metadata/", CapabilityStatementView.as_view(), name="fhir-capability"),
    path("fhir/patients/<int:patient_id>/summary/", PatientSummaryExportView.as_view(), name="fhir-patient-summary"),
    path("terminology/concepts/", TerminologySearchView.as_view(), name="terminology-search"),
    path("terminology/concepts/manage/", TerminologyConceptManageView.as_view(), name="terminology-create"),
    path("terminology/concepts/<int:pk>/", TerminologyConceptManageView.as_view(), name="terminology-update"),
    path("outbox/", OutboxEventListView.as_view(), name="outbox-events"),
]
