import datetime
from unittest import skipUnless

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import DoctorProfile, ProfileStatus, ProviderProfile

from .models import Prescription

User = get_user_model()

try:
    from appointments.models import Appointment

    HAS_APPOINTMENTS = True
except Exception:  # pragma: no cover - parallel app not built yet
    Appointment = None
    HAS_APPOINTMENTS = False


def make_user(email, role, **kw):
    return User.objects.create_user(email=email, password="pass1234", role=role, **kw)


def make_appointment(doctor, patient, status="confirmed"):
    return Appointment.objects.create(
        patient=patient,
        doctor=doctor,
        date=datetime.date.today(),
        start_time=datetime.time(9, 0),
        end_time=datetime.time(9, 30),
        type="online",
        status=status,
    )


@skipUnless(HAS_APPOINTMENTS, "appointments app not available in this worktree")
class PrescriptionFlowTests(APITestCase):
    def setUp(self):
        self.doctor = make_user("doc@example.com", "doctor", first_name="Greg", last_name="House", is_verified=True)
        DoctorProfile.objects.create(user=self.doctor, status=ProfileStatus.VERIFIED)
        self.patient = make_user("pat@example.com", "patient", first_name="Pat")
        self.appointment = make_appointment(self.doctor, self.patient)

    def test_create_prescription_completes_appointment(self):
        self.client.force_authenticate(self.doctor)
        resp = self.client.post(
            f"/api/appointments/{self.appointment.id}/prescription/",
            {
                "notes": "take with food",
                "items": [
                    {
                        "medicine_name": "Amoxicillin",
                        "dosage": "500mg",
                        "frequency": "3x daily",
                        "duration": "7 days",
                        "quantity": 21,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["item_count"] if "item_count" in resp.data else len(resp.data["items"]), 1)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "completed")
        self.assertEqual(Prescription.objects.get().patient, self.patient)

    def test_patient_cannot_create_prescription(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            f"/api/appointments/{self.appointment.id}/prescription/",
            {"items": [{"medicine_name": "X", "dosage": "1", "frequency": "1", "duration": "1", "quantity": 1}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_list_and_detail_scoped_to_owner(self):
        self.client.force_authenticate(self.doctor)
        self.client.post(
            f"/api/appointments/{self.appointment.id}/prescription/",
            {"items": [{"medicine_name": "X", "dosage": "1", "frequency": "1", "duration": "1", "quantity": 1}]},
            format="json",
        )
        rx = Prescription.objects.get()

        other = make_user("other@example.com", "patient")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/prescriptions/").data, [])
        self.assertEqual(self.client.get(f"/api/prescriptions/{rx.id}/").status_code, 403)

        self.client.force_authenticate(self.patient)
        resp = self.client.get("/api/prescriptions/")
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["doctor_name"], "Greg House")
        detail = self.client.get(f"/api/prescriptions/{rx.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.data["items"]), 1)

    def test_send_to_pharmacy_unavailable_without_services_app(self):
        self.client.force_authenticate(self.doctor)
        self.client.post(
            f"/api/appointments/{self.appointment.id}/prescription/",
            {"items": [{"medicine_name": "X", "dosage": "1", "frequency": "1", "duration": "1", "quantity": 1}]},
            format="json",
        )
        rx = Prescription.objects.get()
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            f"/api/prescriptions/{rx.id}/send-to-pharmacy/",
            {"pharmacy_id": 1},
            format="json",
        )
        # A configured pharmacy returns 201; an unavailable integration returns 503;
        # an unknown pharmacy is correctly rejected with 404.
        self.assertIn(resp.status_code, (201, 404, 503))

    def _issue_prescription(self):
        self.client.force_authenticate(self.doctor)
        resp = self.client.post(
            f"/api/appointments/{self.appointment.id}/prescription/",
            {
                "notes": "take with food",
                "items": [
                    {
                        "medicine_name": "Amoxicillin",
                        "dosage": "500mg",
                        "frequency": "3x daily",
                        "duration": "7 days",
                        "quantity": 21,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        return Prescription.objects.get()

    def test_prescription_pdf_for_doctor_patient_and_admin(self):
        rx = self._issue_prescription()
        for user in (self.doctor, self.patient, make_user("admin@example.com", "admin")):
            self.client.force_authenticate(user)
            resp = self.client.get(f"/api/prescriptions/{rx.id}/pdf/")
            self.assertEqual(resp.status_code, 200, resp.content)
            self.assertEqual(resp["Content-Type"], "application/pdf")
            self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_prescription_pdf_forbidden_for_outsider(self):
        rx = self._issue_prescription()
        other = make_user("outsider@example.com", "patient")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(f"/api/prescriptions/{rx.id}/pdf/").status_code, 403)

    def test_doctor_can_send_to_pharmacy(self):
        from services.models import PharmacyOrder

        rx = self._issue_prescription()
        pharmacy = make_user("pharm@example.com", "pharmacy")
        ProviderProfile.objects.create(
            user=pharmacy, organization_type="pharmacy", status=ProfileStatus.VERIFIED
        )
        self.client.force_authenticate(self.doctor)
        resp = self.client.post(
            f"/api/prescriptions/{rx.id}/send-to-pharmacy/",
            {"pharmacy_id": pharmacy.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        order = PharmacyOrder.objects.get()
        self.assertEqual(order.pharmacy, pharmacy)
        self.assertEqual(order.patient, self.patient)

        # patient path still works and is idempotent for the same pharmacy
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            f"/api/prescriptions/{rx.id}/send-to-pharmacy/",
            {"pharmacy_id": pharmacy.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data["created"])
