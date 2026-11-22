import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from accounts.models import User
from appointments.models import Appointment
from clinical.models import ClinicalEncounter, Observation, Referral
from communication.models import Conversation, Message, Notification, NotificationDelivery
from governance.models import Consent
from interoperability.models import OutboxEvent
from prescriptions.models import Prescription, PrescriptionItem
from registry.models import CareRelationship, Organization
from services.models import Bed, CartItem, Supplier, InsuranceClaim, InsurancePolicy, LabOrder, LabResult, LabTest, Medicine, PatientCoverage, PharmacyOrder
from workforce.models import PatientVisit, StaffMembership

from . import models as m
from .integrations import IntegrationUnavailable
from .tasks import deliver_events

BASE = "/api/operations/"


class OperationsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        def user(name, role):
            return User.objects.create_user(email=f"{name}@operations.test", role=role, is_verified=True)
        cls.admin = user("admin", "admin")
        cls.reviewer = user("reviewer", "admin")
        cls.patient = user("patient", "patient")
        cls.other_patient = user("other-patient", "patient")
        cls.doctor = user("doctor", "doctor")
        cls.nurse = user("nurse", "nurse")
        cls.pharmacist = user("pharmacist", "pharmacist")
        cls.witness = user("witness", "pharmacist")
        cls.owner = user("hospital", "hospital")
        cls.pharmacy_owner = user("pharmacy", "pharmacy")
        cls.insurer = user("insurer", "insurance")
        cls.outsider = user("outsider", "doctor")
        cls.hospital = Organization.objects.create(owner=cls.owner, legal_name="Hospital", organization_type="hospital", status="verified")
        cls.pharmacy = Organization.objects.create(owner=cls.pharmacy_owner, legal_name="Pharmacy", organization_type="pharmacy", status="verified")
        cls.insurance = Organization.objects.create(owner=cls.insurer, legal_name="Insurer", organization_type="insurer", status="verified")
        for person, org in [(cls.doctor, cls.hospital), (cls.nurse, cls.hospital), (cls.pharmacist, cls.pharmacy), (cls.witness, cls.pharmacy)]:
            StaffMembership.objects.create(user=person, organization=org, role=person.role)
        cls.bed = Bed.objects.create(hospital=cls.owner, ward="General", label="1")
        cls.bed2 = Bed.objects.create(hospital=cls.owner, ward="General", label="2")
        cls.medicine = Medicine.objects.create(pharmacy=cls.pharmacy_owner, name="Test medicine", price=100, stock=0, sale_type="otc")
        cls.policy = InsurancePolicy.objects.create(provider=cls.insurer, name="Basic", coverage_percent=80)
        cls.coverage = PatientCoverage.objects.create(patient=cls.patient, provider=cls.insurer, policy=cls.policy, member_id="M1")
        cls.appointment = Appointment.objects.create(patient=cls.patient, doctor=cls.doctor, date=timezone.localdate(), start_time="10:00", end_time="10:30", status="confirmed", type="online")
        cls.prescription = Prescription.objects.create(patient=cls.patient, doctor=cls.doctor, appointment=cls.appointment)
        cls.rx_item = PrescriptionItem.objects.create(prescription=cls.prescription, medicine_name="Test medicine", dosage="1 tablet", frequency="daily", route="oral", duration="5 days", quantity=5)
        CareRelationship.objects.create(patient=cls.patient, practitioner=cls.doctor)

    def post(self, path, data, actor=None, expected=201):
        self.client.force_authenticate(actor or self.doctor)
        response = self.client.post(BASE + path, data, format="json")
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def admission(self):
        return self.post("admissions/", {"organization": self.hospital.pk, "patient": self.patient.pk, "attending_doctor": self.doctor.pk, "bed": self.bed.pk, "reason": "Observation"})

    def batch(self, controlled=False):
        return self.post("medicine-batches/", {"organization": self.pharmacy.pk, "medicine": self.medicine.pk,
            "batch_number": "B1", "expires_on": str(timezone.localdate() + timedelta(days=30)), "controlled": controlled}, self.pharmacist)

    def movement(self, batch, quantity, **kwargs):
        actor = kwargs.pop("actor", self.pharmacist)
        expected = kwargs.pop("expected", 200)
        return self.post(f"medicine-batches/{batch['id']}/movement/", {"quantity": quantity,
            "kind": "received" if quantity > 0 else "dispensed", "reason": "Stock workflow", "reference": str(uuid.uuid4()), **kwargs}, actor, expected)

    def test_ward_patient_lookup_is_limited_to_the_selected_facility(self):
        PatientVisit.objects.create(organization=self.hospital, patient=self.patient)
        PatientVisit.objects.create(organization=self.pharmacy, patient=self.other_patient)
        self.client.force_authenticate(self.nurse)
        response = self.client.get(BASE + "context/", {
            "organization": self.hospital.pk, "patient_search": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["patients"], [
            {"id": self.patient.pk, "name": self.patient.display_name},
        ])
        response = self.client.get(BASE + "context/", {
            "organization": self.pharmacy.pk, "patient_search": "",
        })
        self.assertEqual(response.status_code, 403)

    def test_facility_manager_can_review_but_cannot_open_cashier_shifts(self):
        manager = User.objects.create_user(email="manager@operations.test", role="facility_manager")
        StaffMembership.objects.create(user=manager, organization=self.hospital, role=manager.role)
        self.client.force_authenticate(manager)
        self.assertEqual(self.client.get("/api/billing/shifts/").status_code, 200)
        self.assertEqual(self.client.post("/api/billing/shifts/", {"opening_float": 0}).status_code, 403)

    def test_reception_and_receiving_lab_share_an_assigned_visit_handoff(self):
        receptionist = User.objects.create_user(email="handoff@operations.test", role="receptionist")
        StaffMembership.objects.create(user=receptionist, organization=self.hospital, role=receptionist.role)
        lab = User.objects.create_user(email="handoff-lab@operations.test", role="lab", is_verified=True)
        test = LabTest.objects.create(lab=lab, name="Demo assessment", price=100)
        visit = PatientVisit.objects.create(patient=self.patient, organization=self.hospital, status="in_consultation")
        url = f"/api/workforce/visits/{visit.pk}/action/"
        self.client.force_authenticate(receptionist)
        self.assertEqual(self.client.get(url).status_code, 200)
        payload = {"action": "assign_care_team", "assigned_doctor": self.outsider.pk}
        self.assertEqual(self.client.post(url, payload).status_code, 400)
        self.assertEqual(self.client.post(url, {**payload, "assigned_doctor": self.doctor.pk}).status_code, 200)

        order_url = "/api/services/lab-orders/"
        order_payload = {"patient_id": self.patient.pk, "visit_id": visit.pk, "lab_id": lab.pk, "test_id": test.pk}
        self.assertEqual(self.client.post(order_url, order_payload).status_code, 403)
        self.client.force_authenticate(self.doctor)
        order = self.client.post(order_url, order_payload)
        self.assertEqual(order.status_code, 201, order.data)
        visit.refresh_from_db()
        self.assertEqual(visit.status, PatientVisit.Status.LABORATORY)

        self.client.force_authenticate(receptionist)
        arrival = self.client.post(url, {"action": "lab_arrival", "order": order.data["id"]})
        self.assertEqual(arrival.status_code, 200, arrival.data)
        summary = arrival.data["laboratory_handoffs"][0]
        self.assertEqual(set(summary), {"id", "destination", "status", "arrived_at"})
        self.assertTrue(summary["arrived_at"])

        self.client.force_authenticate(lab)
        lab_queue = self.client.get("/api/services/lab-orders/manage/")
        self.assertEqual(parse_datetime(lab_queue.data[0]["arrived_at"]), summary["arrived_at"])
        self.assertEqual(lab_queue.data[0]["visit_number"], visit.visit_number)
        released = self.client.post(f"/api/services/lab-orders/{summary['id']}/update/", {
            "status": "completed", "result_notes": "Demo result",
        })
        self.assertEqual(released.status_code, 200, released.data)
        self.client.force_authenticate(receptionist)
        self.assertEqual(self.client.post(url, {"action": "resume_after_lab"}).status_code, 403)
        self.client.force_authenticate(self.doctor)
        resumed = self.client.post(url, {"action": "resume_after_lab"})
        self.assertEqual(resumed.status_code, 200, resumed.data)
        self.assertEqual(resumed.data["status"], PatientVisit.Status.IN_CONSULTATION)


    @override_settings(LAB_CRITICAL_ESCALATION_MINUTES=30)
    def test_critical_result_escalates_once(self):
        from .tasks import escalate_critical_lab_results

        lab = User.objects.create_user(email="escalation-lab@operations.test", role="lab", is_verified=True)
        test = LabTest.objects.create(lab=lab, name="Demo test", price=100)
        order = LabOrder.objects.create(patient=self.patient, lab=lab, test=test, referring_doctor=self.doctor)
        result = LabResult.objects.create(order=order, name="Demo", value_numeric=2, interpretation="critical",
                                          status="final", released_at=timezone.now() - timedelta(minutes=31))
        self.assertEqual(escalate_critical_lab_results(), 1)
        self.assertEqual(escalate_critical_lab_results(), 0)
        result.refresh_from_db()
        self.assertIsNotNone(result.escalated_at)
        self.assertTrue(Notification.objects.filter(user=self.doctor, kind="laboratory").exists())

    def test_admission_transfer_discharge_and_bed_protection(self):
        admission = self.admission()
        self.bed.refresh_from_db()
        self.assertTrue(self.bed.is_occupied)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(f"/api/services/beds/{self.bed.pk}/toggle/").status_code, 409)
        transfer = self.post(f"admissions/{admission['id']}/transition/", {"action": "transfer", "version": 1, "bed": self.bed2.pk}, expected=200)
        self.bed.refresh_from_db()
        self.bed2.refresh_from_db()
        self.assertFalse(self.bed.is_occupied)
        self.assertTrue(self.bed2.is_occupied)
        self.post(f"admissions/{admission['id']}/transition/", {"action": "discharge", "version": transfer["version"], "summary": "Stable", "follow_up": "Review"}, expected=200)
        self.bed2.refresh_from_db()
        self.assertFalse(self.bed2.is_occupied)
        self.assertEqual(m.WorkflowEvent.objects.filter(resource_type="Admission", action="admission.discharge").count(), 1)

    def test_admission_rejects_duplicate_and_stale_version(self):
        admission = self.admission()
        self.post("admissions/", {"organization": self.hospital.pk, "patient": self.other_patient.pk,
            "attending_doctor": self.doctor.pk, "bed": self.bed.pk, "reason": "Duplicate bed"}, expected=400)
        self.post(f"admissions/{admission['id']}/transition/", {"action": "discharge", "version": 99, "summary": "Stale"}, expected=400)

    def test_organization_isolation_and_suspended_membership(self):
        admission = self.admission()
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(BASE + f"admissions/{admission['id']}/").status_code, 404)
        StaffMembership.objects.filter(user=self.doctor).update(status="suspended")
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get(BASE + f"admissions/{admission['id']}/").status_code, 404)

    def test_dose_is_prescribed_and_only_administered_once(self):
        admission = self.admission()
        dose = self.post("medication-schedules/", {"organization": self.hospital.pk, "admission": admission["id"],
            "prescription": self.prescription.pk, "medication_name": "Test medicine", "dose": "1 tablet", "route": "oral", "due_at": timezone.now().isoformat()})
        self.post(f"medication-schedules/{dose['id']}/administer/", {"status": "given"}, self.nurse, 200)
        self.post(f"medication-schedules/{dose['id']}/administer/", {"status": "given"}, self.nurse, 400)

    def test_dose_rejects_mismatched_prescription(self):
        admission = self.admission()
        self.post("medication-schedules/", {"organization": self.hospital.pk, "admission": admission["id"],
            "prescription": self.prescription.pk, "medication_name": "Wrong medicine", "dose": "1 tablet", "route": "oral", "due_at": timezone.now().isoformat()}, expected=400)

    def test_procedure_overlap_and_lifecycle(self):
        start = timezone.now() + timedelta(days=1)
        payload = {"organization": self.hospital.pk, "patient": self.patient.pk, "surgeon": self.doctor.pk,
            "theatre": "Theatre A", "procedure": "Test procedure", "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}
        procedure = self.post("procedures/", payload)
        self.post("procedures/", payload, expected=400)
        self.post(f"procedures/{procedure['id']}/transition/", {"status": "in_progress"}, expected=200)
        self.post(f"procedures/{procedure['id']}/transition/", {"status": "completed", "notes": "Completed"}, expected=200)

    def test_batch_can_record_audited_opening_stock(self):
        data = {"organization": self.pharmacy.pk, "medicine": self.medicine.pk, "batch_number": "OPEN",
                "expires_on": str(timezone.localdate() + timedelta(days=30)), "opening_quantity": 7}
        batch = self.post("medicine-batches/", data, self.pharmacist)
        self.assertEqual(batch["quantity"], 7)
        self.assertEqual(m.StockMovement.objects.get(batch_id=batch["id"]).reason, "Opening physical stock count")
        self.post("medicine-batches/", {**data, "batch_number": "CONTROLLED", "controlled": True}, self.pharmacist, 400)
        self.assertFalse(m.MedicineBatch.objects.filter(batch_number="CONTROLLED").exists())

    def test_procurement_receipts_are_scoped_and_idempotent(self):
        supplier = Supplier.objects.create(pharmacy=self.pharmacy_owner, suppliername="Supplier", qualification_reference="QUAL-1", qualified_until=timezone.localdate() + timedelta(days=30))
        purchase = self.post("pharmacy-purchases/", {
            "organization": self.pharmacy.pk, "supplier": supplier.pk,
        }, self.pharmacist)
        path = f"pharmacy-purchases/{purchase['id']}/"
        outsider = User.objects.create_user(email="other-pharmacy@operations.test", role="pharmacy")
        self.post(path + "add-line/", {
            "medicine": self.medicine.pk, "ordered": 5, "unit_cost": 80,
        }, outsider, 404)
        line_payload = {"medicine": self.medicine.pk, "ordered": 5, "unit_cost": 80}
        draft_line = self.post(path + "add-line/", line_payload, self.pharmacist)
        removed = self.post(path + "remove-line/", {"line": draft_line["id"]}, self.pharmacist, 200)
        self.assertEqual(removed["lines"], [])
        line = self.post(path + "add-line/", line_payload, self.pharmacist)
        batch = self.post("medicine-batches/", {
            "organization": self.pharmacy.pk, "medicine": self.medicine.pk, "supplier": supplier.pk,
            "batch_number": "PO-1", "expires_on": str(timezone.localdate() + timedelta(days=30)),
        }, self.pharmacist)
        receipt = {
            "line": line["id"], "batch": batch["id"], "quantity": 3,
            "reference": str(uuid.uuid4()), "reason": "Delivery note 1",
        }
        self.post(path + "receive/", receipt, self.pharmacist, 400)
        self.post(path + "transition/", {"action": "approve", "reason": "Reviewed"}, self.pharmacy_owner, 200)
        self.post(path + "receive/", receipt, self.pharmacist, 200)
        replay = self.post(path + "receive/", receipt, self.pharmacist, 200)
        self.assertEqual(replay["lines"][0]["received"], 3)
        self.assertEqual(len(replay["lines"][0]["receipts"]), 1)
        self.post(path + "receive/", {**receipt, "reference": str(uuid.uuid4())}, self.pharmacist, 400)
        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.stock, 3)

    def test_stocktake_requires_independent_review_and_rejects_stale_count(self):
        batch = self.batch()
        self.movement(batch, 5)
        payload = {
            "organization": self.pharmacy.pk, "batch": batch["id"], "counted": 3, "reason": "Shelf count",
        }
        stale = self.post("pharmacy-stocktakes/", payload, self.pharmacist)
        self.movement(batch, 1)
        review = {"action": "approve", "reason": "Checked"}
        self.post(f"pharmacy-stocktakes/{stale['id']}/review/", review, self.witness, 400)
        current = self.post("pharmacy-stocktakes/", payload, self.pharmacist)
        path = f"pharmacy-stocktakes/{current['id']}/review/"
        self.post(path, review, self.pharmacist, 400)
        approved = self.post(path, review, self.witness, 200)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(m.StockMovement.objects.get(pk=approved["adjustment"]).quantity, -3)
        self.post(path, review, self.witness, 400)

    def test_formulary_links_register_and_protects_managed_fields(self):
        from interoperability.models import TerminologyConcept

        concept = TerminologyConcept.objects.create(
            system="https://example.test/register", code="MED-1", display="Test medicine",
            category="registered_medicine_reference",
        )
        payload = {
            "organization": self.pharmacy.pk, "medicine": self.medicine.pk, "strength": "10 mg",
            "dosage_form": "Tablet", "register_entry": concept.pk,
        }
        self.post("pharmacy-formulary/", {**payload, "active": False}, self.pharmacist, 400)
        entry = self.post("pharmacy-formulary/", payload, self.pharmacist)
        self.assertEqual(entry["register_code"], "MED-1")
        updated = self.post(f"pharmacy-formulary/{entry['id']}/configure/", {
            "strength": "10 mg", "dosage_form": "Tablet", "active": False,
        }, self.pharmacist, 200)
        self.assertFalse(updated["active"])
        self.assertIsNone(updated["register_entry"])

    def test_stock_idempotency_and_insufficient_stock(self):
        batch = self.batch()
        reference = str(uuid.uuid4())
        payload = {"quantity": 10, "kind": "received", "reference": reference, "reason": "Received"}
        first = self.post(f"medicine-batches/{batch['id']}/movement/", payload, self.pharmacist, 200)
        second = self.post(f"medicine-batches/{batch['id']}/movement/", payload, self.pharmacist, 200)
        self.assertEqual(first["id"], second["id"])
        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.stock, 10)
        self.movement(batch, -11, expected=400)
        self.post(f"medicine-batches/{batch['id']}/movement/", {**payload, "quantity": 5}, self.pharmacist, 400)

    def test_pharmacist_can_partially_dispense_order_once_per_reference(self):
        batch = self.batch()
        self.movement(batch, 10)
        order = PharmacyOrder.objects.create(
            pharmacy=self.pharmacy_owner, patient=self.patient, prescription_id=self.prescription.pk,
            status=PharmacyOrder.Status.PREPARED,
        )
        url = f"/api/services/pharmacy-orders/{order.pk}/update/"
        self.client.force_authenticate(self.pharmacist)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data[0]["id"], batch["id"])
        review = self.client.post(url.replace("update/", "review/"), {
            "notes": "Reviewed product and patient history", "counselling": "Instructions discussed",
            "product_ids": {str(self.rx_item.pk): self.medicine.pk},
        }, format="json")
        self.assertEqual(review.status_code, 200, review.data)
        data = {
            "status": "dispense", "item": self.rx_item.pk, "batch": batch["id"], "quantity": 2,
            "reason": "Partial fill", "reference": str(uuid.uuid4()),
        }
        for _ in range(2):
            response = self.client.post(url, data, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["prescription_items"][0]["dispensed_quantity"], 2)
        first_movement = response.data["reversible_dispenses"][0]["id"]
        reverse = {"status": "reverse_dispense", "movement": first_movement, "reason": "Recording correction", "unhanded": True}
        for _ in range(2):
            response = self.client.post(url, reverse, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["prescription_items"][0]["dispensed_quantity"], 0)
        response = self.client.post(url, {**data, "reference": str(uuid.uuid4())}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.post(url, {"status": "delivered"}).status_code, 409)
        response = self.client.post(url, {**data, "quantity": 3, "reference": str(uuid.uuid4())}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["prescription_status"], "dispensed")
        self.assertEqual(self.client.post(url, {"status": "delivered", "handover_reference": "Verified collection"}, format="json").status_code, 200)

    def test_recall_blocks_dispensing_and_removes_sellable_stock(self):
        batch = self.batch()
        self.movement(batch, 10)
        self.post(f"medicine-batches/{batch['id']}/transition/", {"action": "recall", "reason": "Supplier notice"}, self.pharmacist, 200)
        self.movement(batch, -1, expected=400)
        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.stock, 0)

    def test_temperature_excursion_quarantines_stock(self):
        batch = self.batch()
        m.MedicineBatch.objects.filter(pk=batch["id"]).update(min_temperature=2, max_temperature=8)
        self.movement(batch, 5)
        response = self.post(f"medicine-batches/{batch['id']}/transition/", {"action": "temperature", "temperature": "12.00"}, self.pharmacist, 200)
        self.assertEqual(response["status"], "quarantined")
        self.assertTrue(m.TemperatureReading.objects.get().excursion)

    def test_controlled_stock_requires_witness_and_tracks_prescription_limit(self):
        batch = self.batch(controlled=True)
        self.movement(batch, 10, expected=400)
        self.movement(batch, 10, witness=self.witness.pk)
        self.movement(batch, -3, witness=self.witness.pk, patient=self.patient.pk, prescription_item=self.rx_item.pk, expected=400)
        order = PharmacyOrder.objects.create(pharmacy=self.pharmacy_owner, patient=self.patient,
            prescription_id=self.prescription.pk, status="prepared")
        self.client.force_authenticate(self.pharmacist)
        path = f"/api/services/pharmacy-orders/{order.pk}/"
        review = self.client.post(path + "review/", {
            "notes": "Reviewed", "counselling": "Discussed",
            "product_ids": {str(self.rx_item.pk): self.medicine.pk},
        }, format="json")
        self.assertEqual(review.status_code, 200, review.data)
        dispense = {"status": "dispense", "item": self.rx_item.pk, "batch": batch["id"], "quantity": 3,
                    "reason": "Controlled fill", "witness": self.witness.pk}
        first = self.client.post(path + "update/", {**dispense, "reference": str(uuid.uuid4())}, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        second = self.client.post(path + "update/", {**dispense, "reference": str(uuid.uuid4())}, format="json")
        self.assertEqual(second.status_code, 400, second.data)
        self.rx_item.refresh_from_db()
        self.assertEqual(self.rx_item.dispensed_quantity, 3)

    def test_approved_substitute_requires_fresh_review_and_exact_product(self):
        original = self.batch()
        self.movement(original, 8)
        replacement = Medicine.objects.create(pharmacy=self.pharmacy_owner, name="Replacement", price=100, sale_type="prescription")
        substitute_batch = m.MedicineBatch.objects.create(
            organization=self.pharmacy, created_by=self.pharmacist, medicine=replacement, batch_number="ALT",
            expires_on=timezone.localdate() + timedelta(days=30), quantity=8,
        )
        order = PharmacyOrder.objects.create(pharmacy=self.pharmacy_owner, patient=self.patient,
            prescription_id=self.prescription.pk, status="prepared")
        path = f"/api/services/pharmacy-orders/{order.pk}/"
        self.client.force_authenticate(self.pharmacist)
        review = {"notes": "Reviewed", "counselling": "Discussed", "product_ids": {str(self.rx_item.pk): self.medicine.pk}}
        self.assertEqual(self.client.post(path + "review/", review, format="json").status_code, 200)
        request = self.client.post(path + "substitutions/", {
            "item": self.rx_item.pk, "replacement": replacement.pk, "reason": "Requested pharmacist review",
        }, format="json")
        self.assertEqual(request.status_code, 201, request.data)
        decision_url = f"/api/services/pharmacy-substitutions/{request.data['id']}/"
        decision = {"decision": "approved", "note": "Confirmed original directions and quantity"}
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.post(decision_url, decision, format="json").status_code, 404)
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.post(decision_url, decision, format="json").status_code, 200)
        self.client.force_authenticate(self.pharmacist)
        data = {"status": "dispense", "item": self.rx_item.pk, "batch": substitute_batch.pk,
                "quantity": 5, "reason": "Approved replacement", "reference": str(uuid.uuid4())}
        self.assertEqual(self.client.post(path + "update/", data, format="json").status_code, 409)
        review["product_ids"][str(self.rx_item.pk)] = replacement.pk
        self.assertEqual(self.client.post(path + "review/", review, format="json").status_code, 200)
        self.assertEqual(self.client.post(path + "update/", {**data, "batch": original["id"]}, format="json").status_code, 409)
        response = self.client.post(path + "update/", data, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["dispensed_batches"][0]["medicine"], replacement.name)

    def test_store_handover_recall_return_and_safety_report(self):
        batch = self.batch()
        self.movement(batch, 8)
        CartItem.objects.create(patient=self.patient, medicine=self.medicine, qty=3)
        self.client.force_authenticate(self.patient)
        checkout = self.client.post("/api/services/orders/checkout/", {}, format="json")
        self.assertEqual(checkout.status_code, 201, checkout.data)
        order_id = checkout.data[0]["id"]
        status_url = f"/api/services/orders/{order_id}/update/"
        movement = m.StockMovement.objects.get(order_id=order_id, kind="dispensed")
        return_payload = {"organization": self.pharmacy.pk, "movement": movement.pk, "quantity": 2,
                          "reason": "Returned product stored in the segregated cabinet"}
        self.post("pharmacy-returns/", return_payload, self.pharmacist, 400)
        self.client.force_authenticate(self.pharmacist)
        for status in ("confirmed", "ready"):
            response = self.client.post(status_url, {"status": status}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.post(status_url, {"status": "delivered"}, format="json").status_code, 400)
        response = self.client.post(status_url, {"status": "delivered", "handover_reference": "Pickup 27"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["dispensed_batches"][0]["id"], movement.pk)
        self.post(f"medicine-batches/{batch['id']}/transition/", {
            "action": "recall", "reason": "Supplier alert",
        }, self.pharmacist, 200)
        contact = m.PharmacyRecallContact.objects.get(batch_id=batch["id"], patient=self.patient)
        contact_url = f"pharmacy-recalls/{contact.pk}/follow_up/"
        for _ in range(2):
            self.post(contact_url, {"action": "notify", "note": "Patient notified"}, self.pharmacist, 200)
        self.assertEqual(Notification.objects.filter(user=self.patient, kind="medicine_recall").count(), 1)
        record = self.post("pharmacy-returns/", return_payload, self.pharmacist)
        self.post("pharmacy-returns/", return_payload, self.pharmacist, 400)
        resolved = self.post(f"pharmacy-returns/{record['id']}/resolve/", {
            "disposition": "destroyed", "note": "Witnessed disposal reference D1",
        }, self.pharmacist, 200)
        self.assertEqual(resolved["disposition"], "destroyed")
        self.assertEqual(m.MedicineBatch.objects.get(pk=batch["id"]).quantity, 5)
        follow_up = self.post(contact_url, {"action": "resolved", "note": "Two units recovered"}, self.pharmacist, 200)
        self.assertEqual((follow_up["handed_over"], follow_up["recovered"]), (3, 2))
        report = self.post("pharmacy-safety-reports/", {
            "organization": self.pharmacy.pk, "movement": movement.pk,
            "kind": "quality_defect", "description": "Reported batch quality concern",
        }, self.pharmacist)
        self.post(f"pharmacy-safety-reports/{report['id']}/resolve/", {
            "state": "reported", "note": "Submitted to the reporting authority", "external_reference": "EXT-1",
        }, self.pharmacist, 200)

    def test_branch_transfer_posts_each_stock_leg_at_the_correct_branch(self):
        from interoperability.models import TerminologyConcept

        source = self.batch()
        self.movement(source, 8)
        other = User.objects.create_user(email="branch@operations.test", role="pharmacy")
        branch = Organization.objects.create(owner=other, legal_name="Other branch", organization_type="pharmacy", status="verified")
        StaffMembership.objects.create(user=self.pharmacist, organization=branch, role="pharmacist")
        product = Medicine.objects.create(pharmacy=other, name=self.medicine.name, price=100, sale_type="otc")
        destination = m.MedicineBatch.objects.create(
            organization=branch, created_by=self.pharmacist, medicine=product, batch_number=source["batch_number"],
            expires_on=source["expires_on"],
        )
        reference = TerminologyConcept.objects.create(system="https://example.test/register", code="P1", display="Test product",
                                                       category="registered_medicine_reference")
        for org, medicine in ((self.pharmacy, self.medicine), (branch, product)):
            m.PharmacyFormularyEntry.objects.create(organization=org, created_by=self.pharmacist, medicine=medicine,
                                                   strength="10 mg", dosage_form="Tablet", register_entry=reference)
        transfer = self.post("pharmacy-transfers/", {
            "organization": self.pharmacy.pk, "source": source["id"], "destination": destination.pk,
            "quantity": 3, "reason": "Replenish branch",
        }, self.pharmacist)
        path = f"pharmacy-transfers/{transfer['id']}/transition/"
        self.post(path, {"action": "receive", "note": "Not dispatched"}, self.pharmacist, 400)
        self.post(path, {"action": "dispatch", "note": "Dispatch reference T1"}, self.pharmacist, 200)
        destination.refresh_from_db()
        self.assertEqual(destination.quantity, 0)
        self.post(path, {"action": "receive", "note": "Received intact"}, self.pharmacist, 200)
        self.post(path, {"action": "receive", "note": "Duplicate receipt"}, self.pharmacist, 400)
        destination.refresh_from_db()
        self.assertEqual(destination.quantity, 3)
        self.assertEqual(m.MedicineBatch.objects.get(pk=source["id"]).quantity, 5)

    def test_checkout_allocates_batches_and_rolls_back_overselling(self):
        batch = self.batch()
        self.movement(batch, 4)
        CartItem.objects.create(patient=self.patient, medicine=self.medicine, qty=5)
        self.client.force_authenticate(self.patient)
        response = self.client.post("/api/services/orders/checkout/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.patient.orders.exists())
        CartItem.objects.filter(patient=self.patient).update(qty=3)
        response = self.client.post("/api/services/orders/checkout/", {}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(m.MedicineBatch.objects.get(pk=batch["id"]).quantity, 1)

    def test_referral_is_accepted_then_closed_by_receiving_clinician(self):
        referral = Referral.objects.create(patient=self.patient, referring_provider=self.doctor, target_specialty="General", reason="Review")
        route = self.post("referrals/", {"organization": self.hospital.pk, "referral": referral.pk})
        for version, status in enumerate(["accepted", "in_progress", "completed"], 1):
            self.post(f"referrals/{route['id']}/transition/", {"version": version, "status": status, "outcome": "Reviewed"}, expected=200)
        referral.refresh_from_db()
        self.assertEqual(referral.status, "completed")

    def test_insurance_annual_limit_and_immutable_decision(self):
        self.post("benefits/", {"organization": self.insurance.pk, "policy": self.policy.pk, "service_code": "CONSULT", "coverage_percent": 80, "annual_limit": 100}, self.insurer)
        amounts = []
        for _ in range(2):
            claim = InsuranceClaim.objects.create(patient=self.patient, provider=self.insurer, policy=self.policy, amount=100)
            assessment = self.post("claim-assessments/", {"organization": self.insurance.pk, "claim": claim.pk, "service_code": "CONSULT"}, self.insurer)
            result = self.post(f"claim-assessments/{assessment['id']}/assess/", {}, self.insurer, 200)
            amounts.append(result["covered_amount"])
            self.post(f"claim-assessments/{assessment['id']}/assess/", {}, self.insurer, 400)
        self.assertEqual(amounts, [80, 20])

    def test_preauthorization_requires_matching_coverage(self):
        auth = self.post("authorizations/", {"organization": self.insurance.pk, "coverage": self.coverage.pk,
            "service_code": "SCAN", "requested_amount": 100, "expires_on": str(timezone.localdate() + timedelta(days=7))}, self.insurer)
        self.post(f"authorizations/{auth['id']}/decide/", {"status": "approved", "approved_amount": 101, "reason": "Too much"}, self.insurer, 400)
        result = self.post(f"authorizations/{auth['id']}/decide/", {"status": "approved", "approved_amount": 80, "reason": "Reviewed"}, self.insurer, 200)
        self.assertEqual(result["approved_amount"], 80)

    def test_identity_merge_is_reversible_without_rewriting_clinical_records(self):
        a = self.post("identities/", {"given_name": "A", "family_name": "Patient"}, self.admin)
        b = self.post("identities/", {"given_name": "B", "family_name": "Patient"}, self.admin)
        self.post(f"identities/{a['id']}/link/", {"patient": self.patient.pk}, self.admin)
        self.post(f"identities/{a['id']}/merge/", {"target": b["id"], "reason": "Verified duplicate"}, self.admin, 200)
        self.assertEqual(m.PatientIdentity.objects.get(patient=self.patient).person_id, a["id"])
        self.post(f"identities/{a['id']}/unmerge/", {"reason": "Incorrect match"}, self.admin, 200)
        self.assertIsNone(m.Person.objects.get(pk=a["id"]).merged_into_id)

    def test_patient_cannot_search_master_identity(self):
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.client.get(BASE + "identities/").status_code, 403)

    def test_imaging_requires_acquired_uid_and_clinician_report(self):
        order = self.post("imaging/", {"organization": self.hospital.pk, "patient": self.patient.pk,
            "referring_doctor": self.doctor.pk, "modality": "US", "body_site": "Abdomen", "indication": "Review"})
        self.post(f"imaging/{order['id']}/transition/", {"version": 1, "status": "reported", "report": "Too early"}, expected=400)
        self.post(f"imaging/{order['id']}/transition/", {"version": 1, "status": "scheduled", "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat()}, expected=200)
        self.post(f"imaging/{order['id']}/transition/", {"version": 2, "status": "acquired", "study_uid": "1.2.840.100"}, expected=200)
        result = self.post(f"imaging/{order['id']}/transition/", {"version": 3, "status": "reported", "report": "Clinician report"}, expected=200)
        self.assertEqual(result["reported_by"], self.doctor.pk)

    def test_rules_need_independent_review_and_report_knowledge_coverage(self):
        rule = self.post("clinical-rules/", {"code": "TEST-ONLY", "version": 1, "kind": "interaction",
            "medicine_a": "A", "medicine_b": "B", "severity": "warning", "message": "Test rule",
            "evidence_url": "https://example.org/evidence"}, self.admin)
        self.post(f"clinical-rules/{rule['id']}/approve/", {}, self.admin, 400)
        self.post(f"clinical-rules/{rule['id']}/approve/", {}, self.reviewer, 200)
        result = self.post("clinical-rules/evaluate/", {"medicines": ["a", "b"]}, self.admin, 200)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertFalse(result["complete_safety_check"])

    @override_settings(OFFLINE_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_offline_changes_are_encrypted_idempotent_and_require_review(self):
        self.admission()
        node = self.post("offline-nodes/", {"organization": self.hospital.pk, "name": "Ward terminal"})
        payload = {"change_id": str(uuid.uuid4()), "patient": self.patient.pk, "kind": "observation",
            "payload": {"category": "vital_signs", "display": "Temperature", "value_numeric": "37.1", "unit": "C", "observed_at": timezone.now().isoformat()}}
        result = self.post(f"offline-nodes/{node['id']}/submit/", payload)
        repeat = self.post(f"offline-nodes/{node['id']}/submit/", payload)
        self.assertEqual(result["id"], repeat["id"])
        self.assertNotIn(b"Temperature", bytes(m.OfflineChange.objects.get().encrypted_payload))
        self.assertFalse(Observation.objects.exists())
        self.post(f"offline-nodes/{node['id']}/review/", {"change": result["id"], "decision": "apply", "reason": "Reviewed source"}, expected=200)
        self.assertEqual(Observation.objects.get().source, "offline_reviewed")

    def test_document_upload_fails_closed_without_scanning(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(BASE + "documents/", {"organization": self.hospital.pk,
            "file": SimpleUploadedFile("test.txt", b"private document")}, format="multipart")
        self.assertEqual(response.status_code, 503, response.data)
        self.assertFalse(m.PrivateDocument.objects.exists())

    def test_outbox_retries_without_claiming_success(self):
        event = OutboxEvent.objects.create(event_type="test", aggregate_type="Test", aggregate_id="1")
        with patch("operations.integrations.deliver_outbox", side_effect=IntegrationUnavailable()):
            self.assertEqual(deliver_events(), {"sent": 0, "failed": 1})
        event.refresh_from_db()
        self.assertEqual(event.status, "failed")
        self.assertIsNotNone(event.next_attempt_at)
        with patch("operations.integrations.deliver_outbox") as deliver:
            deliver_events()
            deliver.assert_not_called()

    def test_configured_sms_provider_records_acknowledgement(self):
        notification = Notification.objects.create(user=self.patient, title="Private clinical update", body="Private detail")
        delivery = NotificationDelivery.objects.create(notification=notification, channel="sms", recipient="+256700000000")
        with override_settings(SMS_WEBHOOK_URL="https://provider.example/send"), patch("operations.integrations.send_notification", return_value="provider-1"):
            call_command("dispatch_notifications", stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.provider_reference, "provider-1")

    def test_research_export_requires_independent_approval_and_suppresses_small_cells(self):
        ClinicalEncounter.objects.create(patient=self.patient, doctor=self.doctor, appointment=self.appointment)
        export = self.post("research-exports/", {"purpose": "Service planning"}, self.admin)
        self.post(f"research-exports/{export['id']}/approve/", {}, self.admin, 400)
        result = self.post(f"research-exports/{export['id']}/approve/", {}, self.reviewer, 200)
        self.assertEqual(result["data"], [])

    def test_copilot_never_activates_without_allowed_adapter_and_review(self):
        self.post("copilot-models/", {"name": "Test", "version": "1", "adapter": "arbitrary.function",
            "evaluation_reference": "Evaluation report"}, self.admin, 400)

    def test_video_recording_requires_both_participants(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(BASE + f"video/{self.appointment.pk}/", {"action": "recording_consent", "consent": True}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["recording_allowed"])
        self.post(f"video/{self.appointment.pk}/", {"action": "recording_consent", "consent": True}, self.doctor, 200)
        self.assertTrue(m.VideoSession.objects.get().doctor_recording_consent)

    def test_message_client_id_deduplicates_retries(self):
        conversation = Conversation.objects.create(patient=self.patient, doctor=self.doctor)
        payload = {"text": "Hello", "client_id": str(uuid.uuid4())}
        self.client.force_authenticate(self.patient)
        first = self.client.post(f"/api/conversations/{conversation.pk}/messages/", payload, format="json")
        second = self.client.post(f"/api/conversations/{conversation.pk}/messages/", payload, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(Message.objects.count(), 1)

    def test_stock_read_excludes_expired_batches_without_waiting_for_worker(self):
        batch = self.batch()
        self.movement(batch, 10)
        m.MedicineBatch.objects.filter(pk=batch["id"]).update(expires_on=timezone.localdate())
        self.client.force_authenticate(self.patient)
        response = self.client.get(f"/api/services/medicines/?pharmacy={self.pharmacy_owner.pk}")
        self.assertEqual(response.data[0]["stock"], 0)

    def test_recalled_batch_cannot_be_quarantined_then_released(self):
        batch = self.batch()
        self.post(f"medicine-batches/{batch['id']}/transition/", {"action": "recall", "reason": "Safety recall"}, self.pharmacist, 200)
        self.post(f"medicine-batches/{batch['id']}/transition/", {"action": "quarantine", "reason": "Attempted bypass"}, self.pharmacist, 400)

    def test_readonly_workflow_state_cannot_be_supplied_during_creation(self):
        self.post("admissions/", {"organization": self.hospital.pk, "patient": self.patient.pk,
            "attending_doctor": self.doctor.pk, "reason": "Test", "status": "discharged"}, expected=400)

    def test_sms_callback_requires_signature_and_is_idempotent(self):
        import hashlib
        import hmac
        import json
        import time
        notification = Notification.objects.create(user=self.patient, title="Update", body="Update")
        delivery = NotificationDelivery.objects.create(notification=notification, channel="sms", status="sent", provider_reference="message-1")
        payload = {"provider_reference": "message-1", "status": "delivered"}
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(BASE + "notification-callback/", payload, format="json").status_code, 403)
        raw = json.dumps(payload)
        timestamp = str(int(time.time()))
        signature = hmac.new(b"callback-test-secret", f"{timestamp}.{raw}".encode(), hashlib.sha256).hexdigest()
        with override_settings(NOTIFICATION_CALLBACK_SECRET="callback-test-secret"):
            for _ in range(2):
                response = self.client.post(BASE + "notification-callback/", raw, content_type="application/json",
                    HTTP_X_MYDOCTOR_TIMESTAMP=timestamp, HTTP_X_MYDOCTOR_SIGNATURE=signature)
                self.assertEqual(response.status_code, 200, response.data)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "delivered")

    def test_signed_document_download_rechecks_membership(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory, override_settings(PRIVATE_MEDIA_ROOT=directory, STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            "private": {"BACKEND": "operations.storage.PrivateLocalStorage"},
        }), patch("operations.integrations.scan_bytes", return_value=True):
            self.client.force_authenticate(self.doctor)
            response = self.client.post(BASE + "documents/", {"organization": self.hospital.pk,
                "file": SimpleUploadedFile("care.txt", b"private care document")}, format="multipart")
            self.assertEqual(response.status_code, 201, response.data)
            link = self.post(f"documents/{response.data['id']}/access-link/", {}, expected=200)
            self.client.force_authenticate(None)
            response = self.client.get(link["url"])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"private care document")
            StaffMembership.objects.filter(user=self.doctor).update(status="suspended")
            self.assertEqual(self.client.get(link["url"]).status_code, 403)

    def test_hie_export_requires_specific_sharing_consent(self):
        self.post(f"hie/patients/{self.patient.pk}/export/", {}, expected=403)
        Consent.objects.create(patient=self.patient, granted_to=self.doctor, consent_type="data_sharing")
        with patch("operations.integrations.request_json", return_value={"receipt": "test"}) as adapter:
            self.post(f"hie/patients/{self.patient.pk}/export/", {}, expected=200)
            self.assertEqual(adapter.call_args.kwargs["data"]["resourceType"], "Bundle")

    def test_missing_external_services_return_unavailable_instead_of_mock_success(self):
        self.client.force_authenticate(self.doctor)
        with override_settings(TERMINOLOGY_SERVER_URL=""):
            response = self.client.get(BASE + "terminology/lookup/", {"system": "http://example.org/codes", "code": "TEST"})
        self.assertEqual(response.status_code, 503, response.data)

    def test_live_video_requires_private_authentication_in_production(self):
        self.client.force_authenticate(self.patient)
        with override_settings(DEBUG=False, JITSI_JWT_SECRET="", JITSI_APP_ID=""):
            self.assertEqual(self.client.get(BASE + f"video/{self.appointment.pk}/").status_code, 503)

    def test_approved_copilot_generates_reviewable_draft_only(self):
        adapter = "operations.integrations.provider_draft"
        with override_settings(COPILOT_ALLOWED_ADAPTERS=[adapter]), patch("operations.integrations.provider_draft", return_value="Administrative draft"):
            model = self.post("copilot-models/", {"name": "Evaluated model", "version": "1", "adapter": adapter, "evaluation_reference": "EVAL-1"}, self.admin)
            self.post(f"copilot-models/{model['id']}/approve/", {}, self.reviewer, 200)
            draft = self.post("copilot-drafts/", {"model": model["id"], "source_text": "Appointment logistics"}, self.admin)
            self.assertEqual(draft["output"], "Administrative draft")
            self.post(f"copilot-drafts/{draft['id']}/review/", {"decision": "accepted", "note": "Reviewed"}, self.admin, 200)
            self.assertFalse(ClinicalEncounter.objects.exists())

    def test_message_sync_and_receipts_are_participant_scoped(self):
        conversation = Conversation.objects.create(patient=self.patient, doctor=self.doctor)
        message = Message.objects.create(conversation=conversation, sender=self.doctor, text="Care update")
        self.client.force_authenticate(self.patient)
        response = self.client.get(f"/api/conversations/{conversation.pk}/sync/?after=0")
        self.assertEqual(response.data["cursor"], message.pk)
        response = self.client.post(f"/api/conversations/{conversation.pk}/sync/", {"phase": "read", "through_id": message.pk}, format="json")
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(f"/api/conversations/{conversation.pk}/sync/").status_code, 403)

    def test_cancelled_batch_order_restores_stock_once(self):
        batch = self.batch()
        self.movement(batch, 5)
        CartItem.objects.create(patient=self.patient, medicine=self.medicine, qty=3)
        self.client.force_authenticate(self.patient)
        response = self.client.post("/api/services/orders/checkout/", {}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        order_id = response.data[0]["id"]
        self.client.force_authenticate(self.pharmacy_owner)
        for _ in range(2):
            response = self.client.post(f"/api/services/orders/{order_id}/update/", {"status": "cancelled"}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(m.MedicineBatch.objects.get(pk=batch["id"]).quantity, 5)
        self.assertEqual(m.StockMovement.objects.filter(order_id=order_id, kind="returned").count(), 1)

    def test_legacy_decision_cannot_bypass_benefit_assessment(self):
        claim = InsuranceClaim.objects.create(patient=self.patient, provider=self.insurer, policy=self.policy, amount=100)
        self.post("claim-assessments/", {"organization": self.insurance.pk, "claim": claim.pk, "service_code": "TEST"}, self.insurer)
        self.client.force_authenticate(self.insurer)
        response = self.client.post(f"/api/services/claims/{claim.pk}/decide/", {"action": "approve"}, format="json")
        self.assertEqual(response.status_code, 409)
        claim.refresh_from_db()
        self.assertEqual(claim.status, "submitted")


import asyncio
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken


class WebSocketTests(TransactionTestCase):
    def setUp(self):
        self.patient = User.objects.create_user(email="socket-patient@test.com", role="patient")
        self.doctor = User.objects.create_user(email="socket-doctor@test.com", role="doctor", is_verified=True)
        self.outsider = User.objects.create_user(email="socket-outsider@test.com", role="patient")
        self.conversation = Conversation.objects.create(patient=self.patient, doctor=self.doctor)

    @override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
    def test_socket_authentication_and_broadcast(self):
        from config.asgi import application
        token = str(AccessToken.for_user(self.patient))
        async def scenario():
            communicator = WebsocketCommunicator(application, f"/ws/conversations/{self.conversation.pk}/", headers=[(b"origin", b"http://localhost:3000")])
            connected, _ = await communicator.connect(timeout=5)
            self.assertTrue(connected)
            await communicator.send_json_to({"type": "authenticate", "access_token": token})
            self.assertEqual((await communicator.receive_json_from(timeout=5))["type"], "ready")
            await get_channel_layer().group_send(f"conversation.{self.conversation.pk}", {"type": "chat.changed", "kind": "message.created", "message_id": 42})
            self.assertEqual(await communicator.receive_json_from(timeout=5), {"type": "message.created", "message_id": 42})
            await communicator.disconnect()
        asyncio.run(scenario())

    def test_socket_rejects_nonparticipant(self):
        from config.asgi import application
        token = str(AccessToken.for_user(self.outsider))
        async def scenario():
            communicator = WebsocketCommunicator(application, f"/ws/conversations/{self.conversation.pk}/", headers=[(b"origin", b"http://localhost:3000")])
            await communicator.connect(timeout=5)
            await communicator.send_json_to({"type": "authenticate", "access_token": token})
            output = await communicator.receive_output(timeout=5)
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], 4403)
            await communicator.disconnect()
        asyncio.run(scenario())
