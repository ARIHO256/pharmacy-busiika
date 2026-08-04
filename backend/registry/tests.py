import datetime

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import ProviderProfile

from .models import CareRelationship, Organization, PractitionerCredential

User = get_user_model()


class RegistryTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="registry-admin@example.com", password="pass123456", role="admin")
        self.doctor = User.objects.create_user(email="registry-doc@example.com", password="pass123456", role="doctor")
        self.hospital = User.objects.create_user(email="registry-hospital@example.com", password="pass123456", role="hospital")
        ProviderProfile.objects.create(user=self.hospital, org_name="Centennial Health Centre")
        self.patient = User.objects.create_user(email="registry-patient@example.com", password="pass123456", role="patient")

    def test_provider_creates_pending_organization_and_admin_verifies(self):
        self.client.force_authenticate(self.hospital)
        response = self.client.post(
            "/api/registry/organizations/",
            {"legal_name": "Centennial Health Centre", "organization_type": "hospital", "license_number": "H-001"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "pending")
        public_id = response.data["public_id"]

        self.client.force_authenticate(self.admin)
        verified = self.client.post(f"/api/registry/organizations/{public_id}/status/", {"status": "verified"}, format="json")
        self.assertEqual(verified.status_code, 200, verified.data)
        self.assertEqual(verified.data["status"], "verified")
        self.hospital.refresh_from_db()
        self.assertTrue(self.hospital.is_verified)
        self.assertEqual(self.hospital.provider_profile.status, "verified")

        self.client.force_authenticate(None)
        listing = self.client.get("/api/registry/organizations/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)

    def test_doctor_submits_credential_and_admin_verifies(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            "/api/registry/credentials/",
            {
                "credential_type": "license",
                "identifier": "MDC-1001",
                "issuer": "Medical Council",
                "issued_on": "2025-01-01",
                "expires_on": "2028-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        credential_id = response.data["id"]

        self.client.force_authenticate(self.admin)
        verified = self.client.post(f"/api/registry/credentials/{credential_id}/verify/", {"status": "verified"}, format="json")
        self.assertEqual(verified.status_code, 200, verified.data)
        self.assertEqual(verified.data["status"], "verified")
        self.assertEqual(PractitionerCredential.objects.get(pk=credential_id).verified_by, self.admin)

    def test_appointment_creates_care_relationship(self):
        from appointments.models import Appointment

        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 30),
            type="online",
            status="confirmed",
        )
        relationship = CareRelationship.objects.create(
            patient=self.patient,
            practitioner=self.doctor,
            appointment=appointment,
            created_by=self.patient,
        )
        self.assertEqual(relationship.status, "active")


class ProtectedRegistryDocumentsTests(APITestCase):
    def setUp(self):
        import shutil
        import tempfile

        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile

        self._media_root = tempfile.mkdtemp(prefix="mydoctor-registry-tests-")
        self._settings = override_settings(MEDIA_ROOT=self._media_root, DEBUG=True)
        self._settings.enable()
        self.addCleanup(self._settings.disable)
        self.addCleanup(shutil.rmtree, self._media_root, True)

        self.admin = User.objects.create_user(
            email="protected-admin@example.com", password="pass123456", role="admin"
        )
        self.owner = User.objects.create_user(
            email="protected-hospital@example.com", password="pass123456", role="hospital"
        )
        ProviderProfile.objects.create(
            user=self.owner,
            org_name="Protected Hospital",
            license_number="PH-001",
        )
        self.organization = Organization.objects.create(
            owner=self.owner,
            legal_name="Protected Hospital",
            organization_type=Organization.Type.HOSPITAL,
            license_number="PH-001",
            license_document=SimpleUploadedFile(
                "facility-license.pdf", b"private facility credential", content_type="application/pdf"
            ),
            status=Organization.Status.VERIFIED,
            active=True,
        )
        self.doctor = User.objects.create_user(
            email="protected-doctor@example.com", password="pass123456", role="doctor"
        )
        self.other_doctor = User.objects.create_user(
            email="other-doctor@example.com", password="pass123456", role="doctor"
        )
        self.credential = PractitionerCredential.objects.create(
            practitioner=self.doctor,
            credential_type=PractitionerCredential.Type.LICENSE,
            identifier="MDC-PROTECTED-1",
            issuer="Medical Council",
            document=SimpleUploadedFile(
                "doctor-license.pdf", b"private professional credential", content_type="application/pdf"
            ),
        )

    def test_credential_document_is_owner_or_admin_only(self):
        url = f"/api/registry/credentials/{self.credential.id}/document/"

        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_authenticate(self.other_doctor)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_authenticate(None)
        direct_media = self.client.get(f"/media/{self.credential.document.name}")
        self.assertEqual(direct_media.status_code, 404)

    def test_organization_document_is_owner_or_admin_only(self):
        url = f"/api/registry/organizations/{self.organization.public_id}/license-document/"

        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

        unrelated = User.objects.create_user(
            email="unrelated-pharmacy@example.com", password="pass123456", role="pharmacy"
        )
        self.client.force_authenticate(unrelated)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_authenticate(None)
        direct_media = self.client.get(f"/media/{self.organization.license_document.name}")
        self.assertEqual(direct_media.status_code, 404)

    def test_suspension_and_reactivation_update_owner_access(self):
        self.owner.is_verified = True
        self.owner.save(update_fields=["is_verified"])
        self.client.force_authenticate(self.admin)

        suspended = self.client.post(
            f"/api/registry/organizations/{self.organization.public_id}/status/",
            {"status": "suspended", "reason": "Licence investigation"},
            format="json",
        )
        self.assertEqual(suspended.status_code, 200, suspended.data)
        self.owner.refresh_from_db()
        self.organization.refresh_from_db()
        self.assertFalse(self.organization.active)
        self.assertFalse(self.owner.is_verified)
        self.assertFalse(self.owner.is_active)

        reactivated = self.client.post(
            f"/api/registry/organizations/{self.organization.public_id}/status/",
            {"status": "reactivate", "reason": "Review completed"},
            format="json",
        )
        self.assertEqual(reactivated.status_code, 200, reactivated.data)
        self.owner.refresh_from_db()
        self.organization.refresh_from_db()
        self.assertTrue(self.organization.active)
        self.assertTrue(self.owner.is_verified)
        self.assertTrue(self.owner.is_active)
