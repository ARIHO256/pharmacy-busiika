import datetime

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
        # Reactivation restores the previously verified status (suspension does
        # not strip verification; the registry reactivation flow asserts the same).
        self.assertEqual(organization.status, Organization.Status.VERIFIED)
        self.assertTrue(organization.active)


class AdminAnalyticsTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", "admin")
        self.patient = make_user("pat@example.com", "patient")
        self.doctor = make_user("doc@example.com", "doctor", first_name="Greg")
        self.today = datetime.date.today()
        from appointments.models import Appointment

        self.completed = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=self.today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            status="completed",
        )
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=self.today,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 30),
            status="missed",
        )

    def test_analytics_requires_admin_role(self):
        resp = self.client.get("/api/admin/analytics/appointments/")
        self.assertEqual(resp.status_code, 401)

        self.client.force_authenticate(self.patient)
        resp = self.client.get("/api/admin/analytics/appointments/")
        self.assertEqual(resp.status_code, 403)

    def test_analytics_shape_and_counts(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(
            f"/api/admin/analytics/appointments/?from={self.today}&to={self.today}"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["total"], 2)
        self.assertEqual(resp.data["totals_by_status"], {"completed": 1, "missed": 1})
        self.assertEqual(resp.data["missed_rate"], 50.0)
        self.assertEqual(len(resp.data["per_day"]), 1)
        self.assertEqual(resp.data["per_day"][0]["total"], 2)
        self.assertEqual(len(resp.data["doctors"]), 1)
        self.assertEqual(resp.data["doctors"][0]["completed"], 1)
        self.assertEqual(resp.data["doctors"][0]["missed"], 1)
        self.assertIn("revenue", resp.data)

    def test_analytics_revenue_counts_paid_appointment_invoices(self):
        from payments.models import Invoice

        Invoice.objects.create(
            patient=self.patient,
            appointment=self.completed,
            amount=50000,
            status="paid",
        )
        Invoice.objects.create(
            patient=self.patient,
            appointment=self.completed,
            amount=20000,
            status="pending",
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.get(
            f"/api/admin/analytics/appointments/?from={self.today}&to={self.today}"
        )
        self.assertEqual(resp.data["revenue"], 50000)

    def test_analytics_rejects_bad_date_range(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/admin/analytics/appointments/?from=not-a-date")
        self.assertEqual(resp.status_code, 400)


class AdminSetRoleTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", "admin")
        self.patient = make_user("pat@example.com", "patient")

    def test_set_role_validates_and_audits(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/admin/users/{self.patient.id}/set-role/",
            {"role": "doctor"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.role, "doctor")
        entry = AuditLog.objects.get(action="user.set_role")
        self.assertEqual(entry.meta["from_role"], "patient")
        self.assertEqual(entry.meta["to_role"], "doctor")

        resp = self.client.post(
            f"/api/admin/users/{self.patient.id}/set-role/",
            {"role": "superuser"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            f"/api/admin/users/{self.admin.id}/set-role/",
            {"role": "patient"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_last_admin_cannot_be_demoted(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/admin/users/{self.admin.id}/set-role/",
            {"role": "patient"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "admin")

        # with a second platform admin, the demotion is allowed
        make_user("admin2@example.com", "admin")
        resp = self.client.post(
            f"/api/admin/users/{self.admin.id}/set-role/",
            {"role": "patient"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_last_admin_cannot_be_suspended(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/admin/users/{self.admin.id}/set-status/",
            {"action": "suspend", "reason": "Housekeeping"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class AdminBroadcastTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", "admin")
        self.patient = make_user("pat@example.com", "patient")
        self.doctor = make_user("doc@example.com", "doctor")
        inactive = make_user("inactive@example.com", "patient")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])

    def test_broadcast_fans_out_to_role_filtered_active_users(self):
        from communication.models import Notification

        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/admin/notifications/broadcast/",
            {"title": "Maintenance", "message": "Sunday night.", "roles": ["patient"]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        # one active patient (the inactive one is skipped)
        self.assertEqual(resp.data["recipients"], 1)
        notification = Notification.objects.get(title="Maintenance")
        self.assertEqual(notification.user, self.patient)
        entry = AuditLog.objects.get(action="notifications.broadcast")
        self.assertEqual(entry.meta["recipients"], 1)

        # no roles filter reaches every active user
        resp = self.client.post(
            "/api/admin/notifications/broadcast/",
            {"title": "Hello", "message": "Everyone"},
            format="json",
        )
        self.assertEqual(resp.data["recipients"], 3)

    def test_broadcast_validates_payload_and_role(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/admin/notifications/broadcast/",
            {"title": "x", "message": "y", "roles": ["bogus"]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(
            "/api/admin/notifications/broadcast/",
            {"title": "", "message": "y"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(
            "/api/admin/notifications/broadcast/",
            {"title": "x", "message": "y", "channels": ["carrier_pigeon"]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            "/api/admin/notifications/broadcast/",
            {"title": "x", "message": "y"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
