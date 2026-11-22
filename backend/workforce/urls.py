from django.urls import path

from .views import (
    DepartmentListCreateView,
    InvitationDetailAcceptView,
    MedicationAdministrationListCreateView,
    NursingNoteListCreateView,
    OperationsSummaryView,
    PatientSearchCreateView,
    StaffListInviteView,
    StaffMembershipStatusView,
    TriageListCreateView,
    VisitActionView,
    VisitListCreateView,
)

urlpatterns = [
    path("departments/", DepartmentListCreateView.as_view(), name="workforce-departments"),
    path("staff/", StaffListInviteView.as_view(), name="workforce-staff"),
    path("staff/<int:pk>/status/", StaffMembershipStatusView.as_view(), name="workforce-staff-status"),
    path("invitations/<uuid:token>/", InvitationDetailAcceptView.as_view(), name="workforce-invitation"),
    path("patients/", PatientSearchCreateView.as_view(), name="workforce-patients"),
    path("visits/", VisitListCreateView.as_view(), name="workforce-visits"),
    path("visits/<int:pk>/action/", VisitActionView.as_view(), name="workforce-visit-action"),
    path("triage/", TriageListCreateView.as_view(), name="workforce-triage"),
    path("nursing-notes/", NursingNoteListCreateView.as_view(), name="workforce-nursing-notes"),
    path("medication-administrations/", MedicationAdministrationListCreateView.as_view(), name="workforce-medication-administrations"),
    path("summary/", OperationsSummaryView.as_view(), name="workforce-summary"),
]
