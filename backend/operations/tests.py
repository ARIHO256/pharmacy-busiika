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
            ActiveRoleContext.objects.create(user=user, context=context)
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
