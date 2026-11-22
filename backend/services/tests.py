import datetime
import unittest

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from .models import (
    CartItem,
    HospitalBooking,
    InsurancePolicy,
    LabOrder,
    LabTest,
    Medicine,
    Order,
    PatientCoverage,
    PharmacyOrder,
)

User = get_user_model()

# Parallel-app models are built by other agents; resolve lazily so these tests
# run standalone.
try:
    from prescriptions.models import Prescription  # noqa: F401

    HAS_PRESCRIPTIONS = True
except Exception:
    HAS_PRESCRIPTIONS = False

try:
    from appointments.models import Appointment  # noqa: F401

    HAS_APPOINTMENTS = True
except Exception:
    HAS_APPOINTMENTS = False

BASE = "/api/services"


def make_user(email, role, **kw):
    return User.objects.create_user(email=email, password="pass1234", role=role, **kw)


class MedicineCrudTests(APITestCase):
    def setUp(self):
        self.pharmacy = make_user("ph@example.com", User.Role.PHARMACY, first_name="City", last_name="Pharmacy")
        self.other_pharmacy = make_user("ph2@example.com", User.Role.PHARMACY)
        self.patient = make_user("pat@example.com", User.Role.PATIENT)
        self.client = APIClient()

    def test_medicine_taxonomy_is_seeded_and_only_a_subcategory_can_be_assigned(self):
        self.client.force_authenticate(self.pharmacy)
        taxonomy = self.client.get(f"{BASE}/medicine-taxonomy/")
        self.assertEqual(taxonomy.status_code, 200)
        self.assertEqual(len(taxonomy.data), 43)
        nodes = {row["node_id"]: row for row in taxonomy.data}
        leaf = next(row for row in taxonomy.data if row["name"] == "Pain Relievers")
        category = nodes[leaf["parent"]]
        self.assertEqual(category["name"], "Over-the-Counter Medications")
        self.assertEqual(nodes[category["parent"]]["level"], 2)
        self.assertTrue(leaf["image_url"])
        payload = {"name": "Catalogue test", "price": 500, "stock": 0}
        rejected = self.client.post(f"{BASE}/medicines/", {**payload, "taxonomy_node": category["node_id"]})
        self.assertEqual(rejected.status_code, 400, rejected.data)
        created = self.client.post(f"{BASE}/medicines/", {**payload, "taxonomy_node": leaf["node_id"]})
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["taxonomy_node"], leaf["node_id"])
        cleared = self.client.put(f"{BASE}/medicines/{created.data['id']}/", {"taxonomy_node": ""}, format="multipart")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data["taxonomy_node"])

    def test_all_subcategories_expose_fields_and_product_values_follow_selected_template(self):
        import json

        self.client.force_authenticate(self.pharmacy)
        nodes = self.client.get(f"{BASE}/medicine-taxonomy/").data
        leaves = [node for node in nodes if node["level"] == 4]
        self.assertEqual(len(leaves), 37)
        for node in leaves:
            keys = [field["key"] for field in node["attribute_fields"]]
            self.assertTrue(keys, node["name"])
            self.assertEqual(len(keys), len(set(keys)), node["name"])
        pain = next(node for node in leaves if node["name"] == "Pain Relievers")
        meter = next(node for node in leaves if node["name"] == "Glucose Meters")
        payload = {"name": "Attribute test", "price": 500, "stock": 0, "taxonomy_node": pain["node_id"]}
        invalid = self.client.post(f"{BASE}/medicines/", {
            **payload, "product_attributes": {"units_per_pack": 0, "compatible_strips": "Test"},
        }, format="json")
        self.assertEqual(invalid.status_code, 400, invalid.data)
        values = {"dosage_form": "Tablet", "units_per_pack": 10}
        created = self.client.post(f"{BASE}/medicines/", {
            **payload, "product_attributes": json.dumps(values),
        }, format="multipart")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["product_attributes"], values)
        url = f"{BASE}/medicines/{created.data['id']}/"
        self.assertEqual(self.client.put(url, {"price": 600}).data["product_attributes"], values)
        changed = self.client.put(url, {
            "taxonomy_node": meter["node_id"], "product_attributes": {"model": "Sample model"},
        }, format="json")
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data["product_attributes"], {"model": "Sample model"})
        self.assertEqual(self.client.put(url, {"taxonomy_node": ""}, format="multipart").data["product_attributes"], {})

    def test_custom_taxonomy_is_pharmacy_scoped_and_archive_keeps_existing_assignments(self):
        from registry.models import Organization

        parent = make_user("hospital@taxonomy.test", User.Role.HOSPITAL)
        facility = Organization.objects.create(owner=parent, legal_name="Hospital", organization_type="hospital", status="verified")
        pharmacy = Organization.objects.create(owner=self.pharmacy, legal_name="Ward pharmacy", organization_type="pharmacy",
                                               status="verified", parent_facility=facility)
        other = Organization.objects.create(owner=self.other_pharmacy, legal_name="Other pharmacy", organization_type="pharmacy",
                                             status="verified")
        manage = f"{BASE}/medicine-taxonomy/manage/"
        self.client.force_authenticate(parent)
        response = self.client.get(manage, {"organization": pharmacy.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get(manage, {"organization": other.pk}).status_code, 403)
        category = next(row for row in response.data["nodes"] if row["name"] == "Over-the-Counter Medications")
        custom = self.client.post(f"{manage}?organization={pharmacy.pk}", {
            "name": "Local products", "level": 4, "parent": category["node_id"],
            "fields": [{"label": "Pack count", "type": "integer"}],
        }, format="json")
        self.assertEqual(custom.status_code, 201, custom.data)
        node_id = custom.data["node_id"]
        node_url = f"{manage}{node_id}/"
        self.client.force_authenticate(self.other_pharmacy)
        self.assertFalse(any(row["node_id"] == node_id for row in self.client.get(f"{BASE}/medicine-taxonomy/").data))
        payload = {"name": "Custom product", "price": 500, "stock": 0, "taxonomy_node": node_id,
                   "product_attributes": {"custom_1": 6}}
        self.assertEqual(self.client.post(f"{BASE}/medicines/", payload, format="json").status_code, 400)
        self.assertEqual(self.client.patch(node_url, {"name": "Changed"}, format="json").status_code, 404)
        self.client.force_authenticate(self.pharmacy)
        created = self.client.post(f"{BASE}/medicines/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(self.client.patch(node_url, {"name": "New local name"}, format="json").status_code, 200)
        category_url = f"{manage}{category['node_id']}/"
        self.assertEqual(self.client.patch(category_url, {"name": "Local OTC", "archived": True}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{BASE}/medicines/", payload, format="json").status_code, 400)
        existing = self.client.put(f"{BASE}/medicines/{created.data['id']}/", {"price": 600}, format="json")
        self.assertEqual(existing.status_code, 200, existing.data)
        self.assertEqual(existing.data["taxonomy_node"], node_id)
        self.assertEqual(existing.data["product_attributes"], {"custom_1": 6})
        self.client.force_authenticate(self.other_pharmacy)
        other_catalogue = {row["node_id"]: row for row in self.client.get(f"{BASE}/medicine-taxonomy/").data}
        self.assertEqual(other_catalogue[category["node_id"]]["name"], category["name"])
        self.assertFalse(other_catalogue[category["node_id"]]["archived"])

    def test_medicine_crud_by_pharmacy(self):
        self.client.force_authenticate(self.pharmacy)
        r = self.client.post(f"{BASE}/medicines/", {"name": "Paracetamol", "price": 500, "stock": 20, "description": "Painkiller"})
        self.assertEqual(r.status_code, 201, r.data)
        med_id = r.data["id"]
        self.assertEqual(Medicine.objects.get(pk=med_id).pharmacy, self.pharmacy)

        r = self.client.put(f"{BASE}/medicines/{med_id}/", {"price": 600, "stock": 15})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["price"], 600)

        # another pharmacy cannot touch it
        self.client.force_authenticate(self.other_pharmacy)
        r = self.client.put(f"{BASE}/medicines/{med_id}/", {"price": 1})
        self.assertEqual(r.status_code, 404)
        r = self.client.delete(f"{BASE}/medicines/{med_id}/")
        self.assertEqual(r.status_code, 404)

        # public list + filters
        self.client.force_authenticate(None)
        r = self.client.get(f"{BASE}/medicines/?pharmacy={self.pharmacy.id}&search=parac")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Paracetamol")

        # patient cannot create
        self.client.force_authenticate(self.patient)
        r = self.client.post(f"{BASE}/medicines/", {"name": "X", "price": 1})
        self.assertEqual(r.status_code, 403)

        # owner delete
        self.client.force_authenticate(self.pharmacy)
        r = self.client.delete(f"{BASE}/medicines/{med_id}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Medicine.objects.filter(pk=med_id).exists())


class CartCheckoutTests(APITestCase):
    def setUp(self):
        self.pharmacy = make_user("ph@example.com", User.Role.PHARMACY)
        self.patient = make_user("pat@example.com", User.Role.PATIENT)
        self.med = Medicine.objects.create(pharmacy=self.pharmacy, name="OTC test product", price=1000, stock=10, sale_type="otc")
        from operations.models import MedicineBatch
        from registry.models import Organization

        org = Organization.objects.create(owner=self.pharmacy, legal_name="Test shop", organization_type="pharmacy", status="verified")
        MedicineBatch.objects.create(
            organization=org, created_by=self.pharmacy, medicine=self.med, batch_number="OTC-1",
            expires_on=datetime.date.today() + datetime.timedelta(days=30), quantity=10,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.patient)

    def test_cart_to_checkout_creates_order_and_decrements_stock(self):
        r = self.client.post(f"{BASE}/cart/", {"medicine_id": self.med.id, "qty": 3})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CartItem.objects.filter(patient=self.patient).count(), 1)

        r = self.client.get(f"{BASE}/cart/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["medicine"]["name"], self.med.name)

        r = self.client.post(f"{BASE}/orders/checkout/", {"delivery": True, "address": "Kampala Rd"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data), 1)
        order = r.data[0]
        self.assertEqual(order["total"], 3000)
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["items"][0]["name"], self.med.name)
        self.assertEqual(order["items"][0]["qty"], 3)

        self.med.refresh_from_db()
        self.assertEqual(self.med.stock, 7)
        self.assertEqual(CartItem.objects.filter(patient=self.patient).count(), 0)

        # pharmacy sees the order and updates status
        self.client.force_authenticate(self.pharmacy)
        r = self.client.get(f"{BASE}/orders/")
        self.assertEqual(len(r.data), 1)
        r = self.client.post(f"{BASE}/orders/{order['id']}/update/", {"status": "confirmed"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "confirmed")
        r = self.client.post(f"{BASE}/orders/{order['id']}/update/", {"status": "bogus"})
        self.assertEqual(r.status_code, 400)

    def test_checkout_rechecks_classification_after_cart_add(self):
        cart_url = f"{BASE}/cart/"
        self.assertEqual(self.client.post(cart_url, {"medicine_id": self.med.pk}).status_code, 201)
        Medicine.objects.filter(pk=self.med.pk).update(sale_type="prescription")
        self.assertEqual(self.client.post(cart_url, {"medicine_id": self.med.pk}).status_code, 409)
        self.assertEqual(self.client.post(f"{BASE}/orders/checkout/", {}).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_standalone_pharmacy_records_payment_and_issues_one_receipt(self):
        from payments.models import Invoice, JournalEntry, PaymentTransaction

        self.client.post(f"{BASE}/cart/", {"medicine_id": self.med.pk, "qty": 2})
        checkout = self.client.post(f"{BASE}/orders/checkout/", {})
        self.assertEqual(checkout.status_code, 201, checkout.data)
        order_id = checkout.data[0]["id"]
        url = f"{BASE}/orders/{order_id}/receipt/"
        cash = {"method": "cash", "amount": 2000}
        self.assertEqual(self.client.post(url, cash).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_authenticate(self.pharmacy)
        for bad in ({"method": "mobile_money", "amount": 2000}, {"method": "cash", "amount": 1000}):
            self.assertEqual(self.client.post(url, bad).status_code, 400)
            self.assertFalse(Invoice.objects.exists())
        receipt = self.client.post(url, cash)
        self.assertEqual(receipt.status_code, 201, receipt.data)
        self.assertEqual(receipt.data["organization_name"], "Test shop")
        self.assertEqual(receipt.data["items"][0]["line_total"], 2000)
        self.assertEqual(receipt.data["payment"]["method"], "cash")

        retry = self.client.post(url, cash)
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(retry.data["number"], receipt.data["number"])
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        self.assertEqual(self.client.post(url, {"method": "card", "amount": 2000, "reference": "TERM-1"}).status_code, 409)
        self.assertEqual(self.client.post(f"{BASE}/orders/{order_id}/update/", {"status": "cancelled"}).status_code, 409)
        entry = JournalEntry.objects.get()
        self.assertTrue(entry.is_balanced)
        self.assertEqual({posting.account.owner_id for posting in entry.postings.all()}, {self.pharmacy.pk})

        self.client.force_authenticate(make_user("other-patient@example.com", User.Role.PATIENT))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.client.get(url).data["number"], receipt.data["number"])
        self.assertTrue(self.client.get(f"{BASE}/orders/").data[0]["payment_recorded"])

    def test_walk_in_cashier_sale_is_atomic_and_reconciles_shift(self):
        import uuid

        from operations.models import StockMovement
        from payments.models import PaymentTransaction
        from workforce.models import StaffMembership

        till = make_user("till@example.com", User.Role.CASHIER)
        organization = self.med.batches.get().organization
        StaffMembership.objects.create(organization=organization, user=till, role="cashier")
        counter = f"{BASE}/pharmacy/counter-sales/"
        shifts = f"{BASE}/pharmacy/shifts/"
        sale = {"request_id": str(uuid.uuid4()), "items": [{"medicine": self.med.pk, "quantity": 2}],
                "method": "cash", "amount": 2000}
        self.assertEqual(self.client.post(counter, sale, format="json").status_code, 403)
        self.client.force_authenticate(till)
        shift = self.client.post(shifts, {"opening_float": 500}, format="json")
        self.assertEqual(shift.status_code, 201, shift.data)
        blocked = Medicine.objects.create(pharmacy=self.pharmacy, name="Restricted", price=500, sale_type="prescription")
        invalid = {**sale, "amount": 2500, "items": [*sale["items"], {"medicine": blocked.pk, "quantity": 1}]}
        self.assertEqual(self.client.post(counter, invalid, format="json").status_code, 400)
        self.assertFalse(Order.objects.exists())
        result = self.client.post(counter, sale, format="json")
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data["receipt"]["patient_name"], "Walk-in customer")
        self.assertEqual(self.client.post(counter, sale, format="json").data, result.data)
        order = Order.objects.get(pk=result.data["order_id"])
        self.assertIsNone(order.patient_id)
        self.assertEqual(order.status, "delivered")
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        self.assertEqual(StockMovement.objects.get(order=order).quantity, -2)
        self.assertEqual(self.med.batches.get().quantity, 8)
        closed = self.client.post(f"{shifts}{shift.data['id']}/close/", {"closing_cash": 2400}, format="json")
        self.assertEqual(closed.status_code, 200, closed.data)
        self.assertEqual((closed.data["expected_cash"], closed.data["variance"]), (2500, -100))
        self.assertEqual(self.client.get(f"{BASE}/orders/{order.pk}/receipt/").status_code, 200)
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.client.get(f"{BASE}/orders/{order.pk}/receipt/").status_code, 404)

    def test_checkout_empty_cart_fails(self):
        r = self.client.post(f"{BASE}/orders/checkout/", {"delivery": False})
        self.assertEqual(r.status_code, 400)
        self.assertIn("detail", r.data)


class LabOrderLifecycleTests(APITestCase):
    def setUp(self):
        self.lab = make_user("lab@example.com", User.Role.LAB, first_name="Med", last_name="Lab", is_verified=True)
        self.patient = make_user("pat@example.com", User.Role.PATIENT, first_name="Jane", last_name="Doe")
        self.client = APIClient()

    def test_lab_order_lifecycle(self):
        # lab creates a test
        self.client.force_authenticate(self.lab)
        r = self.client.post(f"{BASE}/lab-tests/", {"name": "CBC", "price": 20000, "sample_type": "blood"})
        self.assertEqual(r.status_code, 201, r.data)
        test_id = r.data["id"]

        # public catalog
        self.client.force_authenticate(None)
        r = self.client.get(f"{BASE}/lab-tests/?lab={self.lab.id}")
        self.assertEqual(len(r.data), 1)

        # patient books
        self.client.force_authenticate(self.patient)
        r = self.client.post(f"{BASE}/lab-orders/", {"lab_id": self.lab.id, "test_id": test_id})
        self.assertEqual(r.status_code, 201, r.data)
        order_id = r.data["id"]
        self.assertEqual(r.data["status"], "booked")

        r = self.client.get(f"{BASE}/lab-orders/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["test_name"], "CBC")

        # lab manages: move through statuses, attach notes
        self.client.force_authenticate(self.lab)
        r = self.client.get(f"{BASE}/lab-orders/manage/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["patient_name"], "Jane Doe")
        for st in ("sample_collected", "processing"):
            r = self.client.post(f"{BASE}/lab-orders/{order_id}/update/", {"status": st})
            self.assertEqual(r.status_code, 200, r.data)
        r = self.client.post(
            f"{BASE}/lab-orders/{order_id}/update/",
            {"status": "completed", "result_notes": "All normal"},
        )
        self.assertEqual(r.status_code, 200, r.data)
        order = LabOrder.objects.get(pk=order_id)
        self.assertEqual(order.status, "completed")
        self.assertEqual(order.result_notes, "All normal")

        # patient sees the final result
        self.client.force_authenticate(self.patient)
        r = self.client.get(f"{BASE}/lab-orders/")
        self.assertEqual(r.data[0]["status"], "completed")
        self.assertEqual(r.data[0]["result_notes"], "All normal")


class InsuranceTests(APITestCase):
    def setUp(self):
        self.provider = make_user("ins@example.com", User.Role.INSURANCE, first_name="Safe", last_name="Insurance")
        self.patient = make_user("pat@example.com", User.Role.PATIENT)
        self.client = APIClient()

    def test_policy_and_coverage_verify(self):
        # provider creates policy
        self.client.force_authenticate(self.provider)
        r = self.client.post(
            f"{BASE}/policies/",
            {"name": "Gold Plan", "coverage_percent": 80, "premium": 50000, "description": "Full cover"},
        )
        self.assertEqual(r.status_code, 201, r.data)
        policy_id = r.data["id"]

        # public policy list
        self.client.force_authenticate(None)
        r = self.client.get(f"{BASE}/policies/?provider={self.provider.id}")
        self.assertEqual(len(r.data), 1)

        # patient registers coverage
        self.client.force_authenticate(self.patient)
        r = self.client.post(
            f"{BASE}/coverage/",
            {"provider_id": self.provider.id, "policy_id": policy_id, "member_id": "MEM-001"},
        )
        self.assertEqual(r.status_code, 201, r.data)

        r = self.client.get(f"{BASE}/coverage/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["policy_name"], "Gold Plan")

        # public verification
        self.client.force_authenticate(None)
        r = self.client.post(f"{BASE}/coverage/verify/", {"member_id": "MEM-001", "provider_id": self.provider.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"valid": True, "policy": "Gold Plan", "coverage_percent": 80})
        r = self.client.post(f"{BASE}/coverage/verify/", {"member_id": "NOPE", "provider_id": self.provider.id})
        self.assertEqual(r.data, {"valid": False})

    def test_claim_lifecycle(self):
        policy = InsurancePolicy.objects.create(
            provider=self.provider, name="Silver", coverage_percent=60, premium=10000
        )
        PatientCoverage.objects.create(
            patient=self.patient, provider=self.provider, policy=policy, member_id="M1"
        )
        self.client.force_authenticate(self.patient)
        r = self.client.post(
            f"{BASE}/claims/",
            {"provider_id": self.provider.id, "policy_id": policy.id, "amount": 30000},
        )
        self.assertEqual(r.status_code, 201, r.data)
        claim_id = r.data["id"]
        self.assertEqual(r.data["status"], "submitted")

        self.client.force_authenticate(self.provider)
        r = self.client.get(f"{BASE}/claims/manage/")
        self.assertEqual(len(r.data), 1)
        r = self.client.post(f"{BASE}/claims/{claim_id}/decide/", {"action": "approve"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "approved")
        r = self.client.post(f"{BASE}/claims/{claim_id}/decide/", {"action": "nope"})
        self.assertEqual(r.status_code, 400)


class HospitalTests(APITestCase):
    def setUp(self):
        self.hospital = make_user("hosp@example.com", User.Role.HOSPITAL, first_name="General", last_name="Hospital")
        self.patient = make_user("pat@example.com", User.Role.PATIENT)
        self.client = APIClient()

    def test_booking_and_beds(self):
        self.client.force_authenticate(self.hospital)
        r = self.client.post(f"{BASE}/hospital-services/", {"name": "Consultation", "price": 30000})
        self.assertEqual(r.status_code, 201, r.data)
        service_id = r.data["id"]

        r = self.client.post(f"{BASE}/beds/", {"ward": "A", "label": "A-1"})
        self.assertEqual(r.status_code, 201, r.data)
        bed_id = r.data["id"]
        r = self.client.post(f"{BASE}/beds/{bed_id}/toggle/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_occupied"])

        # patients read beds publicly
        self.client.force_authenticate(None)
        r = self.client.get(f"{BASE}/beds/?hospital={self.hospital.id}")
        self.assertEqual(len(r.data), 1)

        # patient books
        self.client.force_authenticate(self.patient)
        r = self.client.post(
            f"{BASE}/hospital-bookings/",
            {"hospital_id": self.hospital.id, "service_id": service_id, "date": "2030-01-10"},
        )
        self.assertEqual(r.status_code, 201, r.data)
        booking_id = r.data["id"]
        self.assertEqual(HospitalBooking.objects.get(pk=booking_id).status, "pending")

        # hospital manages
        self.client.force_authenticate(self.hospital)
        r = self.client.get(f"{BASE}/hospital-bookings/manage/")
        self.assertEqual(len(r.data), 1)
        r = self.client.post(f"{BASE}/hospital-bookings/{booking_id}/update/", {"status": "confirmed"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "confirmed")


@unittest.skipUnless(
    HAS_PRESCRIPTIONS and HAS_APPOINTMENTS,
    "prescriptions/appointments apps not available in this worktree",
)
class PharmacyOrderTests(APITestCase):
    def setUp(self):
        from appointments.models import Appointment
        from prescriptions.models import Prescription, PrescriptionItem

        self.pharmacy = make_user("ph@example.com", User.Role.PHARMACY)
        self.doctor = make_user("doc@example.com", User.Role.DOCTOR)
        self.patient = make_user("pat@example.com", User.Role.PATIENT)
        # Prescription.appointment is a required FK (per SPEC), so create one.
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            type="online",
            status="completed",
        )
        self.prescription = Prescription.objects.create(
            appointment=self.appointment, doctor=self.doctor, patient=self.patient
        )
        PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine_name="Ibuprofen",
            dosage="200mg",
            frequency="2x daily",
            duration="5 days",
            quantity=10,
        )
        self.client = APIClient()

    def test_pharmacy_order_lists_prescription_items(self):
        PharmacyOrder.objects.create(
            pharmacy=self.pharmacy, patient=self.patient, prescription_id=self.prescription.id
        )
        self.client.force_authenticate(self.pharmacy)
        r = self.client.get(f"{BASE}/pharmacy-orders/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["prescription_items"][0]["medicine_name"], "Ibuprofen")
        r = self.client.post(
            f"{BASE}/pharmacy-orders/{r.data[0]['id']}/update/", {"status": "prepared"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "prepared")


class LabResultAccessIsolationTests(APITestCase):
    def setUp(self):
        from registry.models import Organization
        from workforce.models import PatientVisit

        self.lab = make_user("secure-lab@example.com", User.Role.LAB)
        self.patient = make_user("secure-patient@example.com", User.Role.PATIENT)
        self.nurse = make_user(
            "assigned-nurse@example.com", User.Role.NURSE, is_verified=True
        )
        self.other_nurse = make_user(
            "other-nurse@example.com", User.Role.NURSE, is_verified=True
        )
        self.hospital_owner = make_user(
            "secure-hospital@example.com", User.Role.HOSPITAL, is_verified=True
        )
        self.organization = Organization.objects.create(
            owner=self.hospital_owner,
            legal_name="Secure Hospital",
            organization_type=Organization.Type.HOSPITAL,
            status=Organization.Status.VERIFIED,
        )
        PatientVisit.objects.create(
            organization=self.organization,
            patient=self.patient,
            assigned_nurse=self.nurse,
            status=PatientVisit.Status.WAITING_CLINICIAN,
        )
        test = LabTest.objects.create(
            lab=self.lab,
            name="Complete blood count",
            price=20000,
            sample_type="blood",
        )
        self.order = LabOrder.objects.create(
            patient=self.patient,
            lab=self.lab,
            test=test,
        )

    def test_only_assigned_nurse_can_read_patient_lab_order_results(self):
        self.client.force_authenticate(self.nurse)
        allowed = self.client.get(f"{BASE}/lab-orders/{self.order.id}/results/")
        self.assertEqual(allowed.status_code, 200, allowed.data)

        self.client.force_authenticate(self.other_nurse)
        denied = self.client.get(f"{BASE}/lab-orders/{self.order.id}/results/")
        self.assertEqual(denied.status_code, 403, denied.data)

    def test_specimen_recollection_then_critical_result_amendment(self):
        base = f"{BASE}/lab-orders/{self.order.pk}"
        self.order.status = LabOrder.Status.SAMPLE_COLLECTED
        self.order.specimen_id = "SPEC-OLD"
        self.order.save(update_fields=["status", "specimen_id"])
        self.client.force_authenticate(self.lab)
        reject = self.client.post(f"{base}/update/", {"status": "rejected", "rejection_reason": "Container damaged"})
        self.assertEqual(reject.status_code, 200, reject.data)
        result = {"name": "CBC", "value_numeric": "1", "interpretation": "critical", "status": "final"}
        self.assertEqual(self.client.post(f"{base}/results/", result).status_code, 409)
        recollect = self.client.post(f"{base}/update/", {"status": "ready_for_collection"})
        self.assertEqual(recollect.status_code, 200, recollect.data)
        self.assertEqual(recollect.data["specimen_id"], "")
        collected = self.client.post(f"{base}/update/", {"status": "sample_collected", "specimen_id": "SPEC-NEW"})
        self.assertEqual(collected.status_code, 200, collected.data)
        original = self.client.post(f"{base}/results/", result)
        self.assertEqual(original.status_code, 201, original.data)
        amendment = self.client.post(f"{base}/results/", {
            **result, "status": "amended", "value_numeric": "2", "supersedes": original.data["id"],
            "amendment_reason": "Verified transcription correction",
        })
        self.assertEqual(amendment.status_code, 201, amendment.data)
        self.client.force_authenticate(self.other_nurse)
        acknowledge = f"{BASE}/lab-results/{amendment.data['id']}/acknowledge/"
        self.assertEqual(self.client.post(acknowledge).status_code, 403)
        self.client.force_authenticate(self.nurse)
        self.assertEqual(self.client.post(acknowledge).status_code, 200)
        rows = self.client.get(f"{base}/results/").data
        self.assertTrue(rows[0]["is_superseded"])
        self.assertEqual(rows[0]["value_numeric"], "1.0000")
        self.assertTrue(rows[1]["acknowledged"])
