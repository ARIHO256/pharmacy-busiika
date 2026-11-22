from django.urls import path

from .views import (
    AllergyDetailView,
    AllergyListCreateView,
    CarePlanListCreateView,
    ConditionDetailView,
    ConditionListCreateView,
    EncounterDetailView,
    EncounterFinalizeView,
    EncounterAmendView,
    EncounterListCreateView,
    HealthSummaryView,
    MedicationDetailView,
    MedicationListCreateView,
    ObservationListCreateView,
    ReferralListCreateView,
    TimelineView,
)

urlpatterns = [
    path("summary/", HealthSummaryView.as_view()),
    path("timeline/", TimelineView.as_view()),
    path("allergies/", AllergyListCreateView.as_view()),
    path("allergies/<int:pk>/", AllergyDetailView.as_view()),
    path("conditions/", ConditionListCreateView.as_view()),
    path("conditions/<int:pk>/", ConditionDetailView.as_view()),
    path("medications/", MedicationListCreateView.as_view()),
    path("medications/<int:pk>/", MedicationDetailView.as_view()),
    path("observations/", ObservationListCreateView.as_view()),
    path("encounters/", EncounterListCreateView.as_view()),
    path("encounters/<int:pk>/", EncounterDetailView.as_view()),
    path("encounters/<int:pk>/finalize/", EncounterFinalizeView.as_view()),
    path("encounters/<int:pk>/amend/", EncounterAmendView.as_view()),
    path("referrals/", ReferralListCreateView.as_view()),
    path("care-plans/", CarePlanListCreateView.as_view()),
]
