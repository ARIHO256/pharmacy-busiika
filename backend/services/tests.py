import datetime
import unittest

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from .models import (
    CartItem,
    HospitalBooking,
    InsurancePolicy,
    DispensingRecord,
    LabOrder,
    LabTestPanel,
    LabTestPanelItem,
    LabTest,
    Medicine,
    Order,
    PatientCoverage,
    PharmacyOrder,
    SpecimenEvent,
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
        self.med = Medicine.objects.create(pharmacy=self.pharmacy, name="Amoxicillin", price=1000, stock=10)
        self.client = APIClient()
        self.client.force_authenticate(self.patient)

    def test_cart_to_checkout_creates_order_and_decrements_stock(self):
        r = self.client.post(f"{BASE}/cart/", {"medicine_id": self.med.id, "qty": 3})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CartItem.objects.filter(patient=self.patient).count(), 1)

        r = self.client.get(f"{BASE}/cart/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["medicine"]["name"], "Amoxicillin")

        r = self.client.post(f"{BASE}/orders/checkout/", {"delivery": True, "address": "Kampala Rd"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data), 1)
        order = r.data[0]
        self.assertEqual(order["total"], 3000)
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["items"][0]["name"], "Amoxicillin")
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

    def test_checkout_empty_cart_fails(self):
        r = self.client.post(f"{BASE}/orders/checkout/", {"delivery": False})
        self.assertEqual(r.status_code, 400)
        self.assertIn("detail", r.data)


class LabOrderLifecycleTests(APITestCase):
    def setUp(self):
        self.lab = make_user("lab@example.com", User.Role.LAB, first_name="Med", last_name="Lab")
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


class LabPanelAndSpecimenTests(APITestCase):
    def setUp(self):
        self.lab = make_user("panel-lab@example.com", User.Role.LAB, is_verified=True)
        self.patient = make_user("panel-patient@example.com", User.Role.PATIENT)
        self.test_a = LabTest.objects.create(lab=self.lab, name="CBC", price=20000, sample_type="EDTA blood")
        self.test_b = LabTest.objects.create(lab=self.lab, name="Glucose", price=10000, sample_type="Fluoride blood")
        self.client.force_authenticate(self.lab)

    def test_panel_order_creates_individual_orders_and_specimen_timeline(self):
        response = self.client.post(
            f"{BASE}/lab-panels/",
            {
                "name": "Basic wellness",
                "code": "WELLNESS",
                "price": 25000,
                "items": [
                    {"test": self.test_a.id, "sequence": 1, "required": True},
                    {"test": self.test_b.id, "sequence": 2, "required": True},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        panel_id = response.data["id"]
        self.assertEqual(LabTestPanelItem.objects.filter(panel_id=panel_id).count(), 2)

        self.client.force_authenticate(self.patient)
        response = self.client.post(f"{BASE}/lab-panels/{panel_id}/order/", {}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data), 2)
        order_id = response.data[0]["id"]

        self.client.force_authenticate(self.lab)
        response = self.client.post(
            f"{BASE}/lab-orders/{order_id}/specimen-events/",
            {"event_type": "collected", "location": "Collection room", "notes": "Identity checked."},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["barcode"].startswith("LAB-"))
        order = LabOrder.objects.get(pk=order_id)
        self.assertEqual(order.status, LabOrder.Status.SAMPLE_COLLECTED)
        self.assertEqual(SpecimenEvent.objects.filter(order=order).count(), 1)


@unittest.skipUnless(
    HAS_PRESCRIPTIONS and HAS_APPOINTMENTS,
    "prescriptions/appointments apps not available in this worktree",
)
class ClinicalDispensingTests(APITestCase):
    def setUp(self):
        from appointments.models import Appointment
        from prescriptions.models import Prescription, PrescriptionItem

        self.pharmacy = make_user("dispensing-pharmacy@example.com", User.Role.PHARMACY, is_verified=True)
        self.patient = make_user("dispensing-patient@example.com", User.Role.PATIENT)
        self.doctor = make_user("dispensing-doctor@example.com", User.Role.DOCTOR, is_verified=True)
        self.storekeeper = make_user("dispensing-store@example.com", User.Role.STOREKEEPER, is_verified=True)
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 30),
            type="offline",
            status="completed",
        )
        self.prescription = Prescription.objects.create(
            appointment=appointment, doctor=self.doctor, patient=self.patient
        )
        self.item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine_name="Paracetamol",
            dosage="500 mg",
            frequency="three times daily",
            duration="5 days",
            quantity=15,
        )
        self.order = PharmacyOrder.objects.create(
            pharmacy=self.pharmacy, patient=self.patient, prescription_id=self.prescription.id
        )
        Medicine.objects.create(pharmacy=self.pharmacy, name="Paracetamol", price=500, stock=20)

    def test_dispensing_updates_stock_prescription_and_order(self):
        self.client.force_authenticate(self.pharmacy)
        response = self.client.post(
            f"{BASE}/pharmacy-orders/{self.order.id}/dispensing/",
            {
                "status": "dispensed",
                "counselling_notes": "Take after food.",
                "items": [
                    {
                        "prescription_item_id": self.item.id,
                        "medicine_name": "Paracetamol",
                        "prescribed_quantity": 15,
                        "dispensed_quantity": 15,
                        "batch_number": "PCM-001",
                        "label_instructions": "One tablet three times daily.",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], DispensingRecord.Status.DISPENSED)
        self.order.refresh_from_db()
        self.item.refresh_from_db()
        self.prescription.refresh_from_db()
        self.assertEqual(self.order.status, PharmacyOrder.Status.DELIVERED)
        self.assertEqual(self.item.dispensed_quantity, 15)
        self.assertEqual(self.prescription.status, "dispensed")
        self.assertEqual(Medicine.objects.get(pharmacy=self.pharmacy, name="Paracetamol").stock, 5)

    def test_storekeeper_cannot_record_clinical_dispensing(self):
        self.client.force_authenticate(self.storekeeper)
        response = self.client.post(
            f"{BASE}/pharmacy-orders/{self.order.id}/dispensing/",
            {"status": "reviewed", "items": []},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
