from rest_framework.routers import DefaultRouter
from django.urls import path

from . import pharmacy_safety_views as safety, pharmacy_views, views
from .integration_views import DocumentAccess, HIEExport, NotificationCallback, OperationsContext, TerminologyExpand, TerminologyLookup, VideoControl

router = DefaultRouter()
for prefix, view in [
    ("pharmacy-returns", safety.ReturnView),
    ("pharmacy-recalls", safety.RecallContactView),
    ("pharmacy-safety-reports", safety.SafetyReportView),
    ("pharmacy-transfers", safety.TransferView),
    ("pharmacy-purchases", pharmacy_views.ProcurementView),
    ("pharmacy-stocktakes", pharmacy_views.StocktakeView),
    ("pharmacy-formulary", pharmacy_views.FormularyView),
    ("admissions", views.AdmissionView), ("medication-schedules", views.MedicationScheduleView),
    ("procedures", views.ProcedureView), ("medicine-batches", views.BatchView),
    ("referrals", views.ReferralView), ("benefits", views.BenefitView),
    ("authorizations", views.AuthorizationView), ("claim-assessments", views.AssessmentView),
    ("identities", views.PersonView), ("imaging", views.ImagingView),
    ("clinical-rules", views.RuleView), ("offline-nodes", views.OfflineNodeView),
    ("documents", views.DocumentView), ("research-exports", views.ResearchView),
    ("copilot-models", views.CopilotModelView), ("copilot-drafts", views.CopilotDraftView),
]:
    router.register(prefix, view, basename=prefix)

urlpatterns = router.urls + [
    path("context/", OperationsContext.as_view()),
    path("terminology/lookup/", TerminologyLookup.as_view()),
    path("terminology/expand/", TerminologyExpand.as_view()),
    path("hie/patients/<int:patient_id>/export/", HIEExport.as_view()),
    path("video/<int:pk>/", VideoControl.as_view()),
    path("document-access/", DocumentAccess.as_view()),
    path("notification-callback/", NotificationCallback.as_view()),
]
