from django.db.models import Avg
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewPublicSerializer


def _recompute_average_rating(doctor):
    """Update the provider profile used by the public professional directory."""
    try:
        from accounts.models import DoctorProfile, StaffProfile
        avg = round(float(Review.objects.filter(doctor=doctor).aggregate(a=Avg("rating"))["a"] or 0), 2)
        if doctor.role == "doctor":
            DoctorProfile.objects.filter(user=doctor).update(average_rating=avg)
        else:
            StaffProfile.objects.filter(user=doctor).update(average_rating=avg)
    except Exception:
        pass


class AppointmentReviewView(APIView):
    """POST /api/appointments/{id}/review/ — patient reviews completed appointment."""

    permission_classes = [IsRole]
    allowed_roles = ["patient"]

    def post(self, request, pk):
        from appointments.models import Appointment

        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": "appointment not found"}, status=404)
        if appointment.patient_id != request.user.id:
            return Response(
                {"detail": "not the patient of this appointment"}, status=403
            )
        if appointment.status != "completed":
            return Response(
                {"detail": "appointment must be completed"}, status=400
            )
        if Review.objects.filter(appointment=appointment).exists():
            return Response(
                {"detail": "appointment already reviewed"}, status=400
            )

        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = Review.objects.create(
            patient=request.user,
            doctor=appointment.doctor,
            appointment=appointment,
            **serializer.validated_data,
        )
        _recompute_average_rating(appointment.doctor)
        return Response(
            ReviewPublicSerializer(review).data, status=status.HTTP_201_CREATED
        )


class DoctorReviewsListView(generics.ListAPIView):
    """GET /api/doctors/{id}/reviews/ — public."""

    permission_classes = [AllowAny]
    serializer_class = ReviewPublicSerializer

    def get_queryset(self):
        return (
            Review.objects.filter(doctor_id=self.kwargs["pk"])
            .select_related("patient")
            .order_by("-created_at")
        )
