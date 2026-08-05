from django.urls import path

from . import views

urlpatterns = [
    path(
        "appointments/<int:pk>/prescription/",
        views.AppointmentPrescriptionView.as_view(),
    ),
    path("prescriptions/", views.PrescriptionListView.as_view()),
    path("prescriptions/<int:pk>/", views.PrescriptionDetailView.as_view()),
    path("prescriptions/<int:pk>/pdf/", views.PrescriptionPDFView.as_view()),
    path(
        "prescriptions/<int:pk>/send-to-pharmacy/",
        views.SendToPharmacyView.as_view(),
    ),
]
