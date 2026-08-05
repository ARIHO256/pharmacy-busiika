from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from enterprise.models import ActiveRoleContext, RoleContext
from registry.models import Organization
from .models import InventoryBatch, InventoryItem, SurgicalCase, SurgicalChecklist

User = get_user_model()


class OperationsSafetyTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            legal_name="Acceptance Hospital", organization_type="hospital", status="verified"
        )
        self.patient = User.objects.create_user(email="operations.patient@example.test", password="Pass!123456", role="patient")
        self.storekeeper = User.objects.create_user(email="operations.store@example.test", password="Pass!123456", role="storekeeper")
        self.anaesthetist = User.objects.create_user(email="operations.anaesthesia@example.test", password="Pass!123456", role="anaesthetist")
        for user, role in ((self.storekeeper, "storekeeper"), (self.anaesthetist, "anaesthetist")):
            context = RoleContext.objects.create(user=user, organization=self.organization, role_code=role, is_primary=True)
            ActiveRoleContext.objects.update_or_create(user=user, defaults={"context": context})
        self.client = APIClient()

    def test_stock_movement_never_creates_negative_balance(self):
        item = InventoryItem.objects.create(organization=self.organization, name="Test medicine", sku="TEST-001")
        batch = InventoryBatch.objects.create(item=item, batch_number="B-001", quantity_received=5, quantity_available=5)
        self.client.force_authenticate(self.storekeeper)
        response = self.client.post(reverse("operations-inventory-movements"), {
            "batch": batch.id, "movement_type": "issue", "quantity": 6, "reason": "Ward issue",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        batch.refresh_from_db()
        self.assertEqual(batch.quantity_available, 5)

    def test_recalled_batch_cannot_be_dispensed(self):
        item = InventoryItem.objects.create(organization=self.organization, name="Recalled medicine", sku="TEST-002")
        batch = InventoryBatch.objects.create(item=item, batch_number="B-002", quantity_received=10, quantity_available=10, recalled=True)
        self.client.force_authenticate(self.storekeeper)
        response = self.client.post(reverse("operations-inventory-movements"), {
            "batch": batch.id, "movement_type": "dispense", "quantity": 1,
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_theatre_start_requires_named_safety_checks(self):
        case = SurgicalCase.objects.create(
            organization=self.organization, patient=self.patient, procedure_name="Appendicectomy",
            preoperative_diagnosis="Appendicitis", theatre_name="Theatre 1",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2), consent_obtained=True,
        )
        SurgicalChecklist.objects.create(surgical_case=case)
        self.client.force_authenticate(self.anaesthetist)
        response = self.client.post(reverse("operations-surgical-case-action", args=[case.id]), {"action": "start"}, format="json")
        self.assertEqual(response.status_code, 409)
        case.refresh_from_db()
        self.assertNotEqual(case.status, SurgicalCase.Status.IN_THEATRE)

    def test_theatre_schedule_conflict_is_rejected(self):
        start = timezone.now() + timedelta(days=1)
        SurgicalCase.objects.create(
            organization=self.organization, patient=self.patient, procedure_name="First case",
            preoperative_diagnosis="Diagnosis", theatre_name="Theatre 1",
            scheduled_start=start, scheduled_end=start + timedelta(hours=2), status=SurgicalCase.Status.SCHEDULED,
        )
        self.client.force_authenticate(self.anaesthetist)
        response = self.client.post(reverse("operations-surgical-cases"), {
            "patient": self.patient.id, "procedure_name": "Conflicting case", "preoperative_diagnosis": "Diagnosis",
            "theatre_name": "Theatre 1", "scheduled_start": (start + timedelta(minutes=30)).isoformat(),
            "scheduled_end": (start + timedelta(hours=1, minutes=30)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 409)


class SubscriptionBillingTests(TestCase):
    def setUp(self):
        from .models import SubscriptionPlan

        self.patient = User.objects.create_user(
            email="billing.patient@example.test", password="Pass!123456", role="patient"
        )
        self.paid_plan = SubscriptionPlan.objects.create(
            code="pro-monthly",
            name="Professional",
            audience="patient",
            price=50000,
            billing_cycle="monthly",
        )
        self.free_plan = SubscriptionPlan.objects.create(
            code="free",
            name="Free",
            audience="patient",
            price=0,
            billing_cycle="monthly",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.patient)

    def test_paid_plan_activates_only_after_payment(self):
        from payments.models import Invoice
        from .models import AccountSubscription

        response = self.client.post(
            "/api/operations/subscriptions/",
            {"plan": self.paid_plan.id, "method": "mobile_money"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "trial")
        self.assertEqual(response.data["amount"], 50000)
        self.assertTrue(response.data["mock"])
        checkout_url = response.data["checkout_url"]
        subscription_id = response.data["id"]

        invoice = Invoice.objects.get(number=response.data["invoice_number"])
        self.assertEqual(invoice.source_type, "subscription")
        self.assertEqual(invoice.source_id, str(subscription_id))
        self.assertEqual(invoice.items.get().unit_price, 50000)

        # gateway (mock) confirms the payment
        self.client.force_authenticate(None)
        response = self.client.post(checkout_url)
        self.assertEqual(response.status_code, 200)

        subscription = AccountSubscription.objects.get(pk=subscription_id)
        self.assertEqual(subscription.status, "active")
        self.assertGreater(subscription.ends_at, timezone.now() + timedelta(days=25))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")

    def test_free_plan_is_active_immediately(self):
        response = self.client.post(
            "/api/operations/subscriptions/", {"plan": self.free_plan.id}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "active")
        self.assertNotIn("invoice_number", response.data)

    def test_expiry_task_creates_renewal_invoice_once(self):
        from payments.models import Invoice
        from .models import AccountSubscription
        from .tasks import expire_subscriptions_and_scan_stock

        subscription = AccountSubscription.objects.create(
            user=self.patient,
            plan=self.paid_plan,
            status=AccountSubscription.Status.ACTIVE,
            ends_at=timezone.now() + timedelta(days=2),
            auto_renew=True,
        )
        result = expire_subscriptions_and_scan_stock()
        self.assertEqual(result["renewal_invoices_created"], 1)
        invoice = Invoice.objects.get(
            source_type="subscription", source_id=str(subscription.id)
        )
        self.assertEqual(invoice.status, "pending")
        self.assertEqual(invoice.amount, 50000)
        self.assertEqual(invoice.patient, self.patient)

        # a second run does not duplicate the pending renewal invoice
        result = expire_subscriptions_and_scan_stock()
        self.assertEqual(result["renewal_invoices_created"], 0)
        self.assertEqual(
            Invoice.objects.filter(
                source_type="subscription", source_id=str(subscription.id)
            ).count(),
            1,
        )


class ComplaintTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="complaints.admin@example.test", password="Pass!123456", role="admin"
        )
        self.patient = User.objects.create_user(
            email="complaints.patient@example.test", password="Pass!123456", role="patient"
        )
        self.doctor = User.objects.create_user(
            email="complaints.doctor@example.test", password="Pass!123456", role="doctor"
        )
        self.client = APIClient()

    def _create_complaint(self):
        self.client.force_authenticate(self.patient)
        return self.client.post(
            "/api/operations/complaints/",
            {
                "category": "service",
                "description": "The doctor never showed up.",
                "against_user": self.doctor.id,
            },
            format="json",
        )

    def test_user_creates_and_lists_only_own_complaints(self):
        response = self._create_complaint()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "open")
        self.assertEqual(response.data["complainant"], self.patient.id)

        other = User.objects.create_user(
            email="complaints.other@example.test", password="Pass!123456", role="patient"
        )
        self.client.force_authenticate(other)
        response = self.client.get("/api/operations/complaints/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        self.client.force_authenticate(self.patient)
        response = self.client.get("/api/operations/complaints/")
        self.assertEqual(len(response.data), 1)

        # admins see every complaint
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/operations/complaints/")
        self.assertEqual(len(response.data), 1)

    def test_admin_actions_change_status_and_notify_parties(self):
        from communication.models import Notification
        from .models import Complaint

        complaint_id = self._create_complaint().data["id"]

        # non-admins cannot run moderation actions
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            f"/api/operations/complaints/{complaint_id}/action/",
            {"action": "start_review"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f"/api/operations/complaints/{complaint_id}/action/",
            {"action": "bogus"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            f"/api/operations/complaints/{complaint_id}/action/",
            {"action": "start_review"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "in_review")
        complaint = Complaint.objects.get(pk=complaint_id)
        self.assertEqual(complaint.handled_by, self.admin)

        response = self.client.post(
            f"/api/operations/complaints/{complaint_id}/action/",
            {"action": "resolve", "resolution_notes": "Refund issued."},
            format="json",
        )
        self.assertEqual(response.data["status"], "resolved")
        complaint.refresh_from_db()
        self.assertEqual(complaint.resolution_notes, "Refund issued.")

        # complainant and against_user were notified of both status changes
        self.assertEqual(
            Notification.objects.filter(
                user=self.patient, title="Complaint updated"
            ).count(),
            2,
        )
        self.assertEqual(
            Notification.objects.filter(
                user=self.doctor, title="Complaint updated"
            ).count(),
            2,
        )
