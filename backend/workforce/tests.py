from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PatientProfile, StaffProfile, User
from registry.models import Organization, PractitionerCredential

from .models import PatientVisit, StaffMembership, TriageRecord

PASSWORD = "StrongPass123!"


class WorkforceRoleWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="facility-owner@example.com",
            password=PASSWORD,
            role=User.Role.HOSPITAL,
            first_name="Facility",
            last_name="Owner",
            is_verified=True,
        )
        self.organization = Organization.objects.create(
            owner=self.owner,
            legal_name="MyDoctor General Hospital",
            organization_type=Organization.Type.HOSPITAL,
            license_number="HOSP-001",
            status=Organization.Status.VERIFIED,
            active=True,
        )
        self.patient = User.objects.create_user(
            email="patient-workflow@example.com",
            password=PASSWORD,
            role=User.Role.PATIENT,
            first_name="Jane",
            last_name="Patient",
            phone="0700000101",
            is_verified=True,
        )
        PatientProfile.objects.create(user=self.patient, location="Kampala")

    def invite(self, role, email):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/workforce/staff/",
            {
                "email": email,
                "first_name": role.replace("_", " ").title(),
                "last_name": "User",
                "role": role,
                "job_title": role.replace("_", " ").title(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["token"]

    def accept_non_professional(self, token):
        self.client.force_authenticate(None)
        response = self.client.post(
            f"/api/workforce/invitations/{token}/",
            {
                "password": PASSWORD,
                "first_name": "Front",
                "last_name": "Desk",
                "phone": "0700000202",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return User.objects.get(pk=response.data["user"]["id"])

    def accept_nurse(self, token):
        self.client.force_authenticate(None)
        licence = SimpleUploadedFile(
            "nurse-licence.pdf", b"%PDF-1.4 nurse", content_type="application/pdf"
        )
        response = self.client.post(
            f"/api/workforce/invitations/{token}/",
            {
                "password": PASSWORD,
                "first_name": "Nora",
                "last_name": "Nurse",
                "phone": "0700000303",
                "university": "Nursing Institute",
                "year_of_completion": 2022,
                "qualification": "Diploma in Nursing",
                "registration_number": "NMC-2022-1",
                "license_issuer": "Nursing Council",
                "license_expires_on": "2030-12-31",
                "license_document": licence,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return User.objects.get(pk=response.data["user"]["id"])

    def test_nonprofessional_staff_is_facility_scoped_and_ready_immediately(self):
        token = self.invite(User.Role.RECEPTIONIST, "reception@example.com")
        receptionist = self.accept_non_professional(token)

        self.assertTrue(receptionist.is_verified)
        profile = StaffProfile.objects.get(user=receptionist)
        self.assertEqual(profile.status, "verified")
        membership = StaffMembership.objects.get(user=receptionist)
        self.assertEqual(membership.organization, self.organization)
        self.assertEqual(membership.role, User.Role.RECEPTIONIST)
        self.assertEqual(membership.status, StaffMembership.Status.ACTIVE)

    def test_professional_staff_is_pending_until_admin_verifies_licence(self):
        token = self.invite(User.Role.NURSE, "nurse@example.com")
        nurse = self.accept_nurse(token)
        self.assertFalse(nurse.is_verified)
        self.assertEqual(nurse.staff_profile.status, "pending")

        visit = PatientVisit.objects.create(
            organization=self.organization,
            patient=self.patient,
            status=PatientVisit.Status.WAITING_TRIAGE,
            reason="Fever",
        )
        self.client.force_authenticate(nurse)
        response = self.client.post(
            "/api/workforce/triage/",
            {"visit": visit.id, "level": "yellow", "chief_complaint": "Fever"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        admin = User.objects.create_user(
            email="verification-admin@example.com",
            password=PASSWORD,
            role=User.Role.ADMIN,
            is_verified=True,
            is_staff=True,
        )
        credential = PractitionerCredential.objects.get(practitioner=nurse)
        self.client.force_authenticate(admin)
        response = self.client.post(
            f"/api/registry/credentials/{credential.id}/verify/",
            {"status": "verified"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        nurse.refresh_from_db()
        self.assertTrue(nurse.is_verified)
        self.client.force_authenticate(nurse)
        response = self.client.post(
            "/api/workforce/triage/",
            {
                "visit": visit.id,
                "level": "yellow",
                "chief_complaint": "Fever and weakness",
                "temperature_c": "38.4",
                "pulse_bpm": 102,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(TriageRecord.objects.filter(visit=visit, nurse=nurse).exists())
        visit.refresh_from_db()
        self.assertEqual(visit.status, PatientVisit.Status.WAITING_CLINICIAN)

    def test_receptionist_registers_and_checks_in_patient_but_cannot_write_triage(self):
        token = self.invite(User.Role.RECEPTIONIST, "reception-flow@example.com")
        receptionist = self.accept_non_professional(token)
        self.client.force_authenticate(receptionist)

        registration = self.client.post(
            "/api/workforce/patients/",
            {
                "first_name": "Walk",
                "last_name": "In",
                "email": "walkin@example.com",
                "phone": "0700000404",
                "location": "Wakiso",
            },
            format="json",
        )
        self.assertEqual(registration.status_code, 201, registration.data)

        check_in = self.client.post(
            "/api/workforce/visits/",
            {
                "patient": registration.data["id"],
                "visit_type": "walk_in",
                "priority": "routine",
                "reason": "General consultation",
            },
            format="json",
        )
        self.assertEqual(check_in.status_code, 201, check_in.data)
        self.assertGreater(check_in.data["queue_number"], 0)
        self.assertEqual(check_in.data["status"], PatientVisit.Status.WAITING_TRIAGE)

        response = self.client.post(
            "/api/workforce/triage/",
            {
                "visit": check_in.data["id"],
                "level": "green",
                "chief_complaint": "Routine review",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_facility_membership_suspension_does_not_globally_disable_account(self):
        token = self.invite(User.Role.RECEPTIONIST, "multi-facility@example.com")
        receptionist = self.accept_non_professional(token)
        membership = StaffMembership.objects.get(user=receptionist)

        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f"/api/workforce/staff/{membership.id}/status/",
            {"status": StaffMembership.Status.SUSPENDED},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        receptionist.refresh_from_db()
        self.assertTrue(receptionist.is_active)
        membership.refresh_from_db()
        self.assertEqual(membership.status, StaffMembership.Status.SUSPENDED)


    def test_structured_handover_is_saved_and_scope_is_enforced(self):
        nurse = User.objects.create_user(email="handover-nurse@example.com", role=User.Role.NURSE, is_verified=True)
        outsider = User.objects.create_user(email="outside-nurse@example.com", role=User.Role.NURSE, is_verified=True)
        StaffMembership.objects.create(user=nurse, organization=self.organization, role=nurse.role)
        visit = PatientVisit.objects.create(patient=self.patient, organization=self.organization)
        fields = {"situation": "Awaiting review", "assessment": "Observations recorded", "next_actions": "Ward nurse to follow up"}
        url = "/api/workforce/nursing-notes/"
        self.client.force_authenticate(nurse)
        response = self.client.post(url, {"visit": visit.pk, "note_type": "handover", "note": fields["situation"], "handover": fields}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["handover"], fields)
        response = self.client.get(url, {"note_type": "handover"})
        self.assertEqual(len(response.data), 1)
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get(url, {"visit": visit.pk}).status_code, 403)
