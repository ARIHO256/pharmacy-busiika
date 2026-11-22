from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from accounts.models import ProviderProfile
from registry.models import Organization

from .models import AuditLog
from .services import log_action

User = get_user_model()


def make_user(email, role, **kw):
    return User.objects.create_user(email=email, password="pass1234", role=role, **kw)


class AdminAccessTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", "admin")
        self.patient = make_user("pat@example.com", "patient")

    def test_overview_requires_admin_role(self):
        resp = self.client.get("/api/admin/overview/")
        self.assertEqual(resp.status_code, 401)

        self.client.force_authenticate(self.patient)
        resp = self.client.get("/api/admin/overview/")
        self.assertEqual(resp.status_code, 403)

        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/admin/overview/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("users", resp.data)
        self.assertIn("revenue", resp.data)
        self.assertIn("commissions", resp.data)
        self.assertIn("pending_verifications", resp.data)
        self.assertIn("pending_payouts", resp.data)
        self.assertEqual(resp.data["users"].get("patient"), 1)

    def test_users_list_and_role_filter(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/admin/users/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

        resp = self.client.get("/api/admin/users/?role=patient")
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["email"], "pat@example.com")

    def test_set_status_suspend_activate_and_audit(self):
        self.client.force_authenticate(self.admin)

        resp = self.client.post(
            f"/api/admin/users/{self.patient.id}/set-status/",
            {"action": "suspend", "reason": "Administrative suspension test"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)

        resp = self.client.post(
            f"/api/admin/users/{self.patient.id}/set-status/",
            {"action": "activate"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_active)

        resp = self.client.post(
            f"/api/admin/users/{self.patient.id}/set-status/",
            {"action": "bogus"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

        # two audit entries (suspend + activate), bogus not logged
        self.assertEqual(AuditLog.objects.count(), 2)
        resp = self.client.get("/api/admin/audit/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]["action"], "user.activate")
        self.assertEqual(resp.data[1]["action"], "user.suspend")

    def test_log_action_helper(self):
        entry = log_action(self.admin, "test.event", {"k": 1})
        self.assertIsNotNone(entry)
        self.assertEqual(AuditLog.objects.get().meta, {"k": 1})

    def test_provider_status_actions_synchronize_registry(self):
        provider = make_user("lab-provider@example.com", "lab")
        ProviderProfile.objects.create(
            user=provider,
            organization_type=ProviderProfile.OrganizationType.LABORATORY,
            org_name="Trust Lab",
            license_number="LAB-TRUST-1",
            license_document=SimpleUploadedFile(
                "trust-lab-license.pdf",
                b"%PDF-1.4 fake",
                content_type="application/pdf",
            ),
            district="Kampala",
            address="Plot 8 Laboratory Road",
            services_description="Clinical laboratory and diagnostic services",
        )
        self.client.force_authenticate(self.admin)

        verified = self.client.post(
            f"/api/admin/users/{provider.id}/set-status/",
            {"action": "verify"},
            format="json",
        )
        self.assertEqual(verified.status_code, 200, verified.data)
        organization = Organization.objects.get(owner=provider)
        self.assertEqual(organization.status, Organization.Status.VERIFIED)
        self.assertTrue(organization.active)

        suspended = self.client.post(
            f"/api/admin/users/{provider.id}/set-status/",
            {"action": "suspend", "reason": "Credential review required"},
            format="json",
        )
        self.assertEqual(suspended.status_code, 200, suspended.data)
        organization.refresh_from_db()
        self.assertEqual(organization.status, Organization.Status.SUSPENDED)
        self.assertFalse(organization.active)

        activated = self.client.post(
            f"/api/admin/users/{provider.id}/set-status/",
            {"action": "activate"},
            format="json",
        )
        self.assertEqual(activated.status_code, 200, activated.data)
        organization.refresh_from_db()
        self.assertEqual(organization.status, Organization.Status.PENDING)
        self.assertTrue(organization.active)
