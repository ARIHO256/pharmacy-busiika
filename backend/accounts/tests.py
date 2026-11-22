from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from registry.models import Organization

from .models import DoctorProfile, PatientProfile, ProviderProfile, User

REGISTER_URL = "/api/auth/register/"
ME_PROFILE_URL = "/api/auth/me/profile/"
DOCTORS_URL = "/api/doctors/"
VERIFY_UPLOAD_URL = "/api/doctors/verify-upload/"


class RegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_patient_returns_user_tokens_and_profile(self):
        resp = self.client.post(
            REGISTER_URL,
            {
                "email": "patient@example.com",
                "password": "StrongPass123!",
                "first_name": "Pat",
                "last_name": "Ient",
                "phone": "0700000000",
                "role": "patient",
                "location": "Kampala",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn("user", resp.data)
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])
        self.assertIn("refresh", resp.data["tokens"])
        user = User.objects.get(email="patient@example.com")
        self.assertEqual(user.role, "patient")
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())

        # tokens actually work
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {resp.data['tokens']['access']}"
        )
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["email"], "patient@example.com")

    def test_register_duplicate_email_returns_400(self):
        User.objects.create_user(
            email="dup@example.com", password="StrongPass123!", role="patient"
        )
        resp = self.client.post(
            REGISTER_URL,
            {"email": "dup@example.com", "password": "StrongPass123!", "role": "patient"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.data)

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            REGISTER_URL,
            {"email": "weak@example.com", "password": "password", "role": "patient"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="weak@example.com").exists())

    def test_register_provider_creates_provider_profile(self):
        licence = SimpleUploadedFile(
            "pharmacy-license.pdf", b"%PDF-1.4 fake", content_type="application/pdf"
        )
        resp = self.client.post(
            REGISTER_URL,
            {
                "email": "pharm@example.com",
                "password": "StrongPass123!",
                "first_name": "City",
                "last_name": "Pharmacy",
                "phone": "0700111222",
                "role": "pharmacy",
                "organization_name": "City Pharmacy",
                "license_number": "PHA-001",
                "license_document": licence,
                "district": "Kampala",
                "address": "Plot 1 Health Road",
                "services_description": "Prescription dispensing and medicine delivery",
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        user = User.objects.get(email="pharm@example.com")
        profile = ProviderProfile.objects.get(user=user)
        self.assertEqual(profile.status, "pending")
        self.assertEqual(
            profile.organization_type, ProviderProfile.OrganizationType.PHARMACY
        )
        organization = Organization.objects.get(owner=user)
        self.assertEqual(organization.organization_type, Organization.Type.PHARMACY)
        self.assertEqual(organization.status, Organization.Status.PENDING)

    def test_register_clinic_is_counted_as_clinic_not_hospital(self):
        licence = SimpleUploadedFile(
            "clinic-license.pdf", b"%PDF-1.4 fake", content_type="application/pdf"
        )
        response = self.client.post(
            REGISTER_URL,
            {
                "email": "clinic@example.com",
                "password": "StrongPass123!",
                "first_name": "Hope",
                "last_name": "Clinic",
                "phone": "0700111999",
                "role": "hospital",
                "organization_type": "clinic",
                "organization_name": "Hope Clinic",
                "license_number": "CLINIC-001",
                "license_document": licence,
                "district": "Kampala",
                "address": "Wandegeya",
                "services_description": "Outpatient and maternal care",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="clinic@example.com")
        profile = ProviderProfile.objects.get(user=user)
        self.assertEqual(
            profile.organization_type, ProviderProfile.OrganizationType.CLINIC
        )
        self.assertEqual(
            Organization.objects.get(owner=user).organization_type,
            Organization.Type.CLINIC,
        )


class DoctorPublicListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.doctor = User.objects.create_user(
            email="doc@example.com",
            password="StrongPass123!",
            role="doctor",
            first_name="Greg",
            last_name="House",
        )
        self.profile = DoctorProfile.objects.create(
            user=self.doctor,
            specialization="Cardiology",
            hospital="Mulago",
            experience_years=10,
            fees=50000,
            bio="Heart specialist",
        )

    def test_doctor_not_in_public_list_until_verified(self):
        resp = self.client.get(DOCTORS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

        detail = self.client.get(f"{DOCTORS_URL}{self.doctor.id}/")
        self.assertEqual(detail.status_code, 404)
        self.assertIn("detail", detail.data)

        # verify -> appears in list and detail
        self.profile.status = "verified"
        self.profile.save()
        self.doctor.is_verified = True
        self.doctor.save(update_fields=["is_verified"])
        resp = self.client.get(DOCTORS_URL)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertEqual(row["id"], self.doctor.id)
        self.assertEqual(row["first_name"], "Greg")
        self.assertEqual(row["specialization"], "Cardiology")
        self.assertEqual(row["fees"], 50000)

        detail = self.client.get(f"{DOCTORS_URL}{self.doctor.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["status"], "verified")

    def test_doctor_list_search_and_fee_filters(self):
        self.profile.status = "verified"
        self.profile.save()
        self.doctor.is_verified = True
        self.doctor.save(update_fields=["is_verified"])

        resp = self.client.get(DOCTORS_URL, {"search": "cardio"})
        self.assertEqual(len(resp.data), 1)
        resp = self.client.get(DOCTORS_URL, {"search": "house"})
        self.assertEqual(len(resp.data), 1)
        resp = self.client.get(DOCTORS_URL, {"search": "neurology"})
        self.assertEqual(len(resp.data), 0)
        resp = self.client.get(DOCTORS_URL, {"min_fee": 40000, "max_fee": 60000})
        self.assertEqual(len(resp.data), 1)
        resp = self.client.get(DOCTORS_URL, {"min_fee": 60000})
        self.assertEqual(len(resp.data), 0)


class MyProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def test_patient_profile_roundtrip(self):
        user = User.objects.create_user(
            email="p@example.com", password="StrongPass123!", role="patient"
        )
        PatientProfile.objects.create(user=user)
        self._auth(user)

        resp = self.client.get(ME_PROFILE_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["blood_group"], "")

        resp = self.client.patch(
            ME_PROFILE_URL,
            {"blood_group": "O+", "gender": "female", "allergies": "Peanuts"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["blood_group"], "O+")
        self.assertEqual(resp.data["gender"], "female")

        profile = PatientProfile.objects.get(user=user)
        self.assertEqual(profile.allergies, "Peanuts")

    def test_doctor_profile_roundtrip_and_verify_upload(self):
        user = User.objects.create_user(
            email="d@example.com", password="StrongPass123!", role="doctor"
        )
        DoctorProfile.objects.create(user=user, fees=30000)
        self._auth(user)

        resp = self.client.patch(
            ME_PROFILE_URL,
            {"specialization": "Dermatology", "fees": 45000, "status": "verified"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = DoctorProfile.objects.get(user=user)
        self.assertEqual(profile.specialization, "Dermatology")
        self.assertEqual(profile.fees, 45000)
        # status is read-only for self-update
        self.assertEqual(profile.status, "pending")

        license_file = SimpleUploadedFile(
            "license.pdf", b"%PDF-1.4 fake", content_type="application/pdf"
        )
        resp = self.client.post(
            VERIFY_UPLOAD_URL,
            {"license_number": "MDC-9001", "license_document": license_file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile.refresh_from_db()
        self.assertTrue(profile.license_document.name.startswith("doctors/licenses/"))
        self.assertEqual(profile.status, "pending")

    def test_verify_upload_requires_doctor_role(self):
        user = User.objects.create_user(
            email="notdoc@example.com", password="StrongPass123!", role="patient"
        )
        self._auth(user)
        license_file = SimpleUploadedFile(
            "license.pdf", b"fake", content_type="application/pdf"
        )
        resp = self.client.post(
            VERIFY_UPLOAD_URL, {"license_document": license_file}, format="multipart"
        )
        self.assertEqual(resp.status_code, 403)

    def test_provider_profile_roundtrip(self):
        user = User.objects.create_user(
            email="lab@example.com", password="StrongPass123!", role="lab"
        )
        ProviderProfile.objects.create(user=user)
        self._auth(user)
        resp = self.client.patch(
            ME_PROFILE_URL,
            {"org_name": "City Lab", "license_number": "LAB-123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["org_name"], "City Lab")
        self.assertEqual(resp.data["status"], "pending")
        organization = Organization.objects.get(owner=user)
        self.assertEqual(organization.legal_name, "City Lab")
        self.assertEqual(organization.license_number, "LAB-123")
        self.assertEqual(organization.organization_type, Organization.Type.LABORATORY)

    def test_provider_profile_rejects_duplicate_registry_licence(self):
        existing_owner = User.objects.create_user(
            email="existing-lab@example.com", password="StrongPass123!", role="lab"
        )
        Organization.objects.create(
            owner=existing_owner,
            legal_name="Existing Laboratory",
            organization_type=Organization.Type.LABORATORY,
            license_number="LAB-DUPLICATE",
        )

        user = User.objects.create_user(
            email="new-lab@example.com", password="StrongPass123!", role="lab"
        )
        ProviderProfile.objects.create(user=user)
        self._auth(user)
        response = self.client.patch(
            ME_PROFILE_URL,
            {"org_name": "New Laboratory", "license_number": "LAB-DUPLICATE"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProviderProfile.objects.get(user=user).license_number, "")
