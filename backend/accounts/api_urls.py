from django.urls import path

from .views import DoctorDetailView, DoctorListView, DoctorVerifyUploadView

urlpatterns = [
    path("doctors/", DoctorListView.as_view(), name="doctor_list"),
    path(
        "doctors/verify-upload/",
        DoctorVerifyUploadView.as_view(),
        name="doctor_verify_upload",
    ),
    path("doctors/<int:pk>/", DoctorDetailView.as_view(), name="doctor_detail"),
]
