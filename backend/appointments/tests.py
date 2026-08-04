import datetime

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import DoctorProfile

from .models import Appointment, Availability

User = get_user_model()

# A Monday well in the future so "skip past times" never interferes.
FUTURE_DATE = datetime.date(2030, 1, 7)  # Monday
WEEKDAY = FUTURE_DATE.weekday()


class BaseSetup(APITestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email="doc@example.com",
            password="pass1234",
            role=User.Role.DOCTOR,
            first_name="Greg",
            last_name="House",
        )
        self.doctor.is_verified = True
        self.doctor.save(update_fields=["is_verified"])
        DoctorProfile.objects.create(
            user=self.doctor,
            status="verified",
            year_of_completion=2015,
            university="Makerere University",
            cadre="medical_officer",
            license_number="MDC-100",
            hospital="MyDoctor Hospital",
            fees=50000,
        )
        self.patient = User.objects.create_user(
            email="pat@example.com",
            password="pass1234",
            role=User.Role.PATIENT,
            first_name="John",
            last_name="Doe",
        )
        self.availability = Availability.objects.create(
            doctor=self.doctor,
            weekday=WEEKDAY,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            slot_minutes=30,
            breaks=[{"start": "10:00", "end": "10:30"}],
        )


class AvailabilityTests(BaseSetup):
    def test_doctor_can_create_and_list_availability(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            "/api/availability/",
            {
                "weekday": 2,
                "start_time": "14:00",
                "end_time": "16:00",
                "slot_minutes": 30,
                "breaks": [{"start": "15:00", "end": "15:15"}],
                "holidays": ["2030-01-02"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["doctor"], self.doctor.id)

        response = self.client.get("/api/availability/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_patient_cannot_create_availability(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/availability/",
            {"weekday": 2, "start_time": "14:00", "end_time": "16:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SlotsTests(BaseSetup):
    def test_slots_computed_and_breaks_excluded(self):
        response = self.client.get(
            f"/api/doctors/{self.doctor.id}/slots/?date={FUTURE_DATE.isoformat()}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        starts = [s["start"] for s in response.data["slots"]]
        self.assertEqual(
            starts, ["09:00", "09:30", "10:30"]
        )  # 10:00 is inside the break

    def test_slots_exclude_booked_appointment(self):
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=FUTURE_DATE,
            start_time=datetime.time(9, 30),
            end_time=datetime.time(10, 0),
        )
        response = self.client.get(
            f"/api/doctors/{self.doctor.id}/slots/?date={FUTURE_DATE.isoformat()}"
        )
        starts = [s["start"] for s in response.data["slots"]]
        self.assertNotIn("09:30", starts)
        self.assertIn("09:00", starts)

    def test_slots_empty_on_holiday(self):
        self.availability.holidays = [FUTURE_DATE.isoformat()]
        self.availability.save()
        response = self.client.get(
            f"/api/doctors/{self.doctor.id}/slots/?date={FUTURE_DATE.isoformat()}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slots"], [])


class BookingFlowTests(BaseSetup):
    def test_book_then_confirm_flow(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/appointments/",
            {
                "doctor_id": self.doctor.id,
                "consent_acknowledged": True,
                "date": FUTURE_DATE.isoformat(),
                "start_time": "09:00",
                "type": "online",
                "reason": "Headache",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["end_time"], "09:30:00")
        self.assertEqual(response.data["patient_name"], "John Doe")
        appointment_id = response.data["id"]

        # Booking the same slot again must fail.
        response = self.client.post(
            "/api/appointments/",
            {
                "doctor_id": self.doctor.id,
                "consent_acknowledged": True,
                "date": FUTURE_DATE.isoformat(),
                "start_time": "09:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Slot not available")

        # Patient cannot confirm their own appointment.
        response = self.client.post(f"/api/appointments/{appointment_id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Doctor confirms.
        self.client.force_authenticate(self.doctor)
        response = self.client.post(f"/api/appointments/{appointment_id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")

        # List endpoints are role-scoped and support ?status=.
        response = self.client.get("/api/appointments/?status=confirmed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["doctor_name"], "Greg House")

    def test_booking_requires_explicit_treatment_consent(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/appointments/",
            {
                "doctor_id": self.doctor.id,
                "date": FUTURE_DATE.isoformat(),
                "start_time": "09:00",
                "type": "online",
                "reason": "Consultation",
                "consent_acknowledged": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_booking_unavailable_slot_rejected(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/appointments/",
            {
                "doctor_id": self.doctor.id,
                "consent_acknowledged": True,
                "date": FUTURE_DATE.isoformat(),
                "start_time": "10:00",  # inside the break window
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Slot not available")

    def test_patient_can_cancel_own_appointment(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=FUTURE_DATE,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
        )
        self.client.force_authenticate(self.patient)
        response = self.client.post(f"/api/appointments/{appointment.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)


class VerificationGateTests(APITestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email="pending-doc@example.com", password="pass1234", role=User.Role.DOCTOR
        )
        DoctorProfile.objects.create(
            user=self.doctor, status="pending", year_of_completion=2020,
            university="Medical University", cadre="medical_officer",
            license_number="PENDING-1", hospital="Pending Clinic", fees=25000,
        )
        self.patient = User.objects.create_user(
            email="booking-patient@example.com", password="pass1234", role=User.Role.PATIENT
        )

    def test_unverified_doctor_cannot_publish_or_receive_bookings(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            "/api/availability/",
            {"weekday": WEEKDAY, "start_time": "09:00", "end_time": "11:00", "slot_minutes": 30},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        Availability.objects.create(
            doctor=self.doctor, weekday=WEEKDAY, start_time=datetime.time(9),
            end_time=datetime.time(11), slot_minutes=30,
        )
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/appointments/",
            {
                "doctor_id": self.doctor.id,
                "consent_acknowledged": True,
                "date": FUTURE_DATE.isoformat(),
                "start_time": "09:00",
                "type": "online",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
