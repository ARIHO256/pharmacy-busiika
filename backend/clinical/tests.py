import datetime

from rest_framework.test import APITestCase

from accounts.models import User
from appointments.models import Appointment
from governance.models import Consent

from .models import ClinicalEncounter, Observation


class ClinicalApiTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient@clinical.test", password="pass12345", role="patient"
        )
        self.doctor = User.objects.create_user(
            email="doctor@clinical.test", password="pass12345", role="doctor"
        )
        self.other_doctor = User.objects.create_user(
            email="other@clinical.test", password="pass12345", role="doctor"
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            type="online",
            status="confirmed",
            reason="Persistent headache",
        )
        Consent.objects.create(
            patient=self.patient,
            granted_to=self.doctor,
            consent_type="treatment",
            purpose="treatment",
            data_categories=["clinical_record"],
        )

    def test_patient_can_create_and_read_structured_allergy(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/clinical/allergies/",
            {"substance": "Penicillin", "reaction": "Rash", "severity": "moderate"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        response = self.client.get("/api/clinical/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["allergies"][0]["substance"], "Penicillin")

    def test_doctor_can_create_and_finalize_encounter(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            "/api/clinical/encounters/",
            {
                "appointment": self.appointment.id,
                "assessment": "Tension headache",
                "treatment_plan": "Hydration, rest and analgesia",
                "safety_net_advice": "Seek urgent care for weakness or confusion",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        encounter_id = response.data["id"]
        response = self.client.post(f"/api/clinical/encounters/{encounter_id}/finalize/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], ClinicalEncounter.Status.FINAL)
        self.assertEqual(response.data["version"], 1)

    def test_unrelated_doctor_is_denied(self):
        self.client.force_authenticate(self.other_doctor)
        response = self.client.get(
            f"/api/clinical/summary/?patient_id={self.patient.id}"
        )
        self.assertEqual(response.status_code, 403)

    def test_doctor_can_record_vital_observation(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            f"/api/clinical/observations/?patient_id={self.patient.id}",
            {
                "patient_id": self.patient.id,
                "category": "vital_signs",
                "code": "systolic-bp",
                "display": "Systolic blood pressure",
                "value_numeric": "135",
                "unit": "mmHg",
                "interpretation": "high",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Observation.objects.count(), 1)

    def test_final_encounter_can_only_change_through_versioned_amendment(self):
        self.client.force_authenticate(self.doctor)
        created = self.client.post(
            "/api/clinical/encounters/",
            {
                "appointment": self.appointment.id,
                "assessment": "Initial assessment",
                "treatment_plan": "Initial plan",
            },
            format="json",
        )
        encounter_id = created.data["id"]
        finalized = self.client.post(f"/api/clinical/encounters/{encounter_id}/finalize/")
        self.assertEqual(finalized.status_code, 200)
        blocked = self.client.patch(
            f"/api/clinical/encounters/{encounter_id}/",
            {"assessment": "Silent overwrite"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 409)
        amended = self.client.post(
            f"/api/clinical/encounters/{encounter_id}/amend/",
            {"reason": "Correction after reviewing the consultation", "assessment": "Corrected assessment"},
            format="json",
        )
        self.assertEqual(amended.status_code, 200, amended.data)
        self.assertEqual(amended.data["status"], ClinicalEncounter.Status.AMENDED)
        self.assertEqual(amended.data["version"], 2)
        self.assertEqual(len(amended.data["revisions"]), 2)
