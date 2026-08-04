from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from appointments.models import Appointment

from .models import AuditEvent, BreakGlassAccess, Consent


class GovernanceApiTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient@gov.test", password="pass12345", role="patient"
        )
        self.doctor = User.objects.create_user(
            email="doctor@gov.test", password="pass12345", role="doctor"
        )
        self.admin = User.objects.create_user(
            email="admin@gov.test", password="pass12345", role="admin"
        )

    def test_patient_can_grant_and_revoke_consent(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/governance/consents/",
            {
                "consent_type": "treatment",
                "purpose": "treatment",
                "data_categories": ["summary", "medications"],
                "granted_to": self.doctor.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        consent_id = response.data["id"]
        response = self.client.post(
            f"/api/governance/consents/{consent_id}/revoke/",
            {"reason": "Changed provider"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Consent.Status.REVOKED)
        self.assertGreaterEqual(AuditEvent.objects.count(), 2)

    def test_doctor_can_start_and_end_break_glass(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            "/api/governance/break-glass/",
            {
                "patient": self.patient.id,
                "reason": "Unconscious patient requires urgent allergy review",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        access_id = response.data["id"]
        response = self.client.post(f"/api/governance/break-glass/{access_id}/end/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], BreakGlassAccess.Status.ENDED)

    def test_unrelated_doctor_cannot_view_patient_consents(self):
        Consent.objects.create(patient=self.patient, consent_type="treatment")
        self.client.force_authenticate(self.doctor)
        response = self.client.get(
            f"/api/governance/patients/{self.patient.id}/consents/"
        )
        self.assertEqual(response.status_code, 403)
