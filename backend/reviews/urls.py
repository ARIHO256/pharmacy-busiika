from django.urls import path

from . import views

urlpatterns = [
    path("appointments/<int:pk>/review/", views.AppointmentReviewView.as_view()),
    path("doctors/<int:pk>/reviews/", views.DoctorReviewsListView.as_view()),
]
