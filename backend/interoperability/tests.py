import datetime

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from appointments.models import Appointment
from clinical.models import Allergy
from governance.models import Consent

from .models import OutboxEvent, TerminologyConcept
from .services import emit_event

User = get_user_model()


class InteroperabilityTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(email="fhir-patient@example.com", password="pass123456", role="patient", first_name="Amina", last_name="N")
        self.doctor = User.objects.create_user(email="fhir-doctor@example.com", password="pass123456", role="doctor")
        self.admin = User.objects.create_user(email="fhir-admin@example.com", password="pass123456", role="admin")
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            type="online",
            status="confirmed",
        )
        Consent.objects.create(
            patient=self.patient,
            granted_to=self.doctor,
            consent_type="telemedicine",
            purpose="treatment",
            data_categories=["patient_summary"],
        )
        Allergy.objects.create(patient=self.patient, substance="Penicillin", reaction="Rash", recorded_by=self.doctor)

    def test_capability_statement_is_public_and_explicitly_draft(self):
        response = self.client.get("/api/interoperability/fhir/metadata/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["resourceType"], "CapabilityStatement")
        self.assertIn("draft", response.data["description"].lower())

    def test_authorized_doctor_can_export_patient_summary(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.get(f"/api/interoperability/fhir/patients/{self.patient.id}/summary/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["resourceType"], "Bundle")
        resource_types = {entry["resource"]["resourceType"] for entry in response.data["entry"]}
        self.assertIn("Patient", resource_types)
        self.assertIn("AllergyIntolerance", resource_types)
        allergy = next(entry["resource"] for entry in response.data["entry"] if entry["resource"]["resourceType"] == "AllergyIntolerance")
        self.assertNotIn(None, allergy.values())
        self.assertEqual(
            allergy["verificationStatus"]["coding"][0]["code"], "unconfirmed"
        )

    def test_doctor_export_does_not_disclose_consent_granted_to_another_doctor(self):
        other_doctor = User.objects.create_user(
            email="other-fhir-doctor@example.com",
            password="pass123456",
            role="doctor",
        )
        other_consent = Consent.objects.create(
            patient=self.patient,
            granted_to=other_doctor,
            consent_type="record_sharing",
            purpose="treatment",
            data_categories=["patient_summary"],
        )

        self.client.force_authenticate(self.doctor)
        response = self.client.get(
            f"/api/interoperability/fhir/patients/{self.patient.id}/summary/"
        )
        self.assertEqual(response.status_code, 200, response.data)

        exported_consents = [
            entry["resource"]
            for entry in response.data["entry"]
            if entry["resource"]["resourceType"] == "Consent"
        ]
        exported_ids = {resource["id"] for resource in exported_consents}
        self.assertNotIn(str(other_consent.id), exported_ids)
        self.assertEqual(len(exported_consents), 1)

    def test_terminology_search_and_outbox(self):
        TerminologyConcept.objects.create(system="urn:test", code="BP", display="Blood pressure", aliases=["BP"])
        response = self.client.get("/api/interoperability/terminology/concepts/?q=pressure")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        event = emit_event("test.created", self.appointment, {"ok": True}, actor=self.doctor, patient=self.patient)
        self.assertEqual(event.status, OutboxEvent.Status.PENDING)
        self.client.force_authenticate(self.admin)
        outbox = self.client.get("/api/interoperability/outbox/")
        self.assertEqual(outbox.status_code, 200)
        self.assertEqual(outbox.data[0]["event_type"], "test.created")
