from django.urls import path

from .views import (
    AuditEventListView,
    BreakGlassEndView,
    BreakGlassListCreateView,
    BreakGlassReviewView,
    ComplianceOverviewView,
    ConsentListCreateView,
    ConsentRevokeView,
    PatientConsentStatusView,
    PrivilegedAccessListCreateView,
    PrivilegedAccessDecisionView,
)

urlpatterns = [
    path("consents/", ConsentListCreateView.as_view()),
    path("consents/<int:pk>/revoke/", ConsentRevokeView.as_view()),
    path("patients/<int:patient_id>/consents/", PatientConsentStatusView.as_view()),
    path("break-glass/", BreakGlassListCreateView.as_view()),
    path("break-glass/<int:pk>/end/", BreakGlassEndView.as_view()),
    path("break-glass/<int:pk>/review/", BreakGlassReviewView.as_view()),
    path("compliance/overview/", ComplianceOverviewView.as_view()),
    path("audit/", AuditEventListView.as_view()),
    path("privileged-access/", PrivilegedAccessListCreateView.as_view(), name="privileged-access-list"),
    path("privileged-access/<int:pk>/decision/", PrivilegedAccessDecisionView.as_view(), name="privileged-access-decision"),
]
