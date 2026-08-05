from django.urls import path

from .views import (
    AppointmentActionView,
    AppointmentListCreateView,
    AppointmentRescheduleView,
    AvailabilityDetailView,
    AvailabilityListCreateView,
    DoctorSlotsView,
)

urlpatterns = [
    path("availability/", AvailabilityListCreateView.as_view()),
    path("availability/<int:pk>/", AvailabilityDetailView.as_view()),
    path("doctors/<int:doctor_id>/slots/", DoctorSlotsView.as_view()),
    path("appointments/", AppointmentListCreateView.as_view()),
    # Explicit action routes only. A generic "<str:action>" route here would
    # greedily shadow /prescription/, /review/ and /video-room/ from other
    # apps (this urls.py is included before theirs in config/urls.py).
    path(
        "appointments/<int:pk>/reschedule/",
        AppointmentRescheduleView.as_view(),
    ),
    path(
        "appointments/<int:pk>/confirm/",
        AppointmentActionView.as_view(action="confirm"),
    ),
    path(
        "appointments/<int:pk>/cancel/",
        AppointmentActionView.as_view(action="cancel"),
    ),
    path(
        "appointments/<int:pk>/complete/",
        AppointmentActionView.as_view(action="complete"),
    ),
    path(
        "appointments/<int:pk>/miss/",
        AppointmentActionView.as_view(action="miss"),
    ),
]
