from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from registry.models import Organization
from services.models import PharmacyOrder

from .models import PatientVisit, StaffMembership


class VisitHandoffTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        owner = self.user("hospital")
        self.facility = Organization.objects.create(
            owner=owner, legal_name="Test Hospital", organization_type="hospital", status="verified",
        )
        self.doctor = self.staff("doctor")
        self.nurse = self.staff("nurse")
        self.reception = self.staff("receptionist")
        self.patient = self.user("patient")
        self.visit = PatientVisit.objects.create(
            organization=self.facility, patient=self.patient, assigned_doctor=self.doctor,
            status=PatientVisit.Status.IN_CONSULTATION,
        )

    def user(self, role, suffix=""):
        return User.objects.create_user(email=f"{role}{suffix}@example.test", role=role, is_verified=True)

    def staff(self, role, suffix=""):
        user = self.user(role, suffix)
        StaffMembership.objects.create(user=user, role=role, organization=self.facility, status="active")
        return user

    def post(self, actor, path, **data):
        self.client.force_authenticate(actor)
        return self.client.post(f"/api/workforce/{path}", data, format="json")

    def route(self, destination, **data):
        return self.post(self.doctor, "handoffs/", visit=self.visit.pk, destination=destination,
                         instructions="Please complete this handoff.", **data)

    def test_parallel_handoffs_return_for_review_and_block_checkout_until_resolved(self):
        nursing = self.route("nursing")
        reception = self.route("reception")
        self.assertEqual(nursing.status_code, 201, nursing.data)
        self.assertEqual(reception.status_code, 201, reception.data)
        path = f"handoffs/{nursing.data['id']}/transition/"
        self.assertEqual(self.post(self.reception, path, action="accept").status_code, 403)
        self.client.force_authenticate(self.reception)
        board = self.client.get(f"/api/workforce/handoffs/?visit={self.visit.pk}").data
        self.assertEqual(next(row for row in board if row["destination"] == "nursing")["instructions"], "")
        self.assertEqual(self.post(self.nurse, path, action="accept").status_code, 200)
        other_nurse = self.staff("nurse", "other")
        self.assertEqual(self.post(other_nurse, path, action="complete", outcome="Done").status_code, 403)
        returned = self.post(self.nurse, path, action="return", outcome="Observations are ready.")
        self.assertEqual(returned.data["status"], "returned")
        checkout = f"visits/{self.visit.pk}/action/"
        self.assertEqual(self.post(self.doctor, checkout, status="completed").status_code, 409)
        self.assertEqual(self.post(self.doctor, path, action="complete", outcome="Reviewed").status_code, 200)
        another = f"handoffs/{reception.data['id']}/transition/"
        self.assertEqual(self.post(self.reception, another, action="accept").status_code, 200)
        self.assertEqual(self.post(self.reception, another, action="complete", outcome="Follow-up booked").status_code, 200)
        self.assertEqual(self.post(self.doctor, checkout, status="completed", checkout_note="Follow-up booked.").status_code, 200)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.checkout_note, "Follow-up booked.")
        self.assertEqual(self.route("reception").status_code, 400)

    def test_walk_in_prescription_routes_only_to_the_facility_pharmacy(self):
        pharmacy = self.user("pharmacy")
        Organization.objects.create(
            owner=pharmacy, parent_facility=self.facility, legal_name="Hospital Dispensary",
            organization_type="pharmacy", status="verified",
        )
        pharmacist = self.staff("pharmacist")
        prescription = self.post(self.doctor, f"visits/{self.visit.pk}/prescription/", items=[{
            "medicine_name": "Test medicine", "dosage": "1 tablet", "frequency": "daily",
            "duration": "3 days", "route": "oral", "quantity": 3,
        }])
        self.assertEqual(prescription.status_code, 201, prescription.data)
        routed = self.route("pharmacy", prescription=prescription.data["id"])
        self.assertEqual(routed.status_code, 201, routed.data)
        order = PharmacyOrder.objects.get(pk=routed.data["pharmacy_order"])
        self.assertEqual(order.pharmacy_id, pharmacy.pk)
        self.assertEqual(order.patient_id, self.patient.pk)
        self.assertEqual(self.route("pharmacy", prescription=prescription.data["id"]).status_code, 400)
        path = f"handoffs/{routed.data['id']}/transition/"
        self.assertEqual(self.post(pharmacist, path, action="accept").status_code, 200)
        self.assertEqual(self.post(pharmacist, path, action="complete", outcome="Done").status_code, 400)

    def test_linked_ward_admission_appears_on_visit_and_blocks_checkout(self):
        self.assertEqual(self.route("ward").status_code, 201)
        self.client.force_authenticate(self.doctor)
        admission = self.client.post("/api/operations/admissions/", {
            "organization": self.facility.pk, "patient": self.patient.pk,
            "attending_doctor": self.doctor.pk, "reason": "Observation", "visit": self.visit.pk,
        }, format="json")
        self.assertEqual(admission.status_code, 201, admission.data)
        board = self.client.get("/api/workforce/visits/").data
        self.assertEqual(board[0]["admission"]["status"], "admitted")
        self.assertEqual(self.client.get(f"/api/workforce/handoffs/?visit={self.visit.pk}").data[0]["status"], "completed")
        checkout = f"visits/{self.visit.pk}/action/"
        self.assertEqual(self.post(self.doctor, checkout, status="completed").status_code, 409)
        discharged = self.client.post(f"/api/operations/admissions/{admission.data['id']}/transition/", {
            "action": "discharge", "version": admission.data["version"], "summary": "Observation complete.",
        }, format="json")
        self.assertEqual(discharged.status_code, 200, discharged.data)
        self.assertEqual(self.post(self.doctor, checkout, status="completed").status_code, 200)

    def test_billing_handoff_requires_a_settled_visit_invoice(self):
        cashier = self.staff("cashier")
        row = self.route("billing")
        self.assertEqual(row.status_code, 201, row.data)
        path = f"handoffs/{row.data['id']}/transition/"
        self.assertEqual(self.post(cashier, path, action="accept").status_code, 200)
        self.assertEqual(self.post(cashier, path, action="complete", outcome="Paid").status_code, 400)
        invoice = self.client.post("/api/billing/invoices/", {
            "patient": self.patient.pk, "visit": self.visit.pk,
            "items": [{"description": "Consultation", "quantity": 1, "unit_price": 10000}],
        }, format="json")
        self.assertEqual(invoice.status_code, 201, invoice.data)
        self.assertEqual(invoice.data["visit"], self.visit.pk)
        self.assertEqual(self.post(cashier, path, action="complete", outcome="Paid").status_code, 400)
        shift = self.client.post("/api/billing/shifts/", {}, format="json")
        self.assertEqual(shift.status_code, 201, shift.data)
        payment = self.client.post(f"/api/billing/invoices/{invoice.data['id']}/payments/", {
            "amount": 10000, "method": "cash",
        }, format="json")
        self.assertEqual(payment.status_code, 201, payment.data)
        self.assertEqual(self.post(cashier, path, action="complete", outcome="Paid").status_code, 200)

    def test_imaging_report_returns_to_assigned_doctor(self):
        from datetime import timedelta
        from django.utils import timezone

        routed = self.route("imaging", modality="US", body_site="Abdomen")
        self.assertEqual(routed.status_code, 201, routed.data)
        record = f"/api/operations/imaging/{routed.data['imaging_order']}/"
        imaging_staff = self.staff("lab_technician")
        self.client.force_authenticate(imaging_staff)
        scheduled = self.client.post(f"{record}transition/", {
            "version": 1, "status": "scheduled",
            "scheduled_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        }, format="json")
        self.assertEqual(scheduled.status_code, 200, scheduled.data)
        acquired = self.client.post(f"{record}transition/", {
            "version": 2, "status": "acquired", "study_uid": "1.2.345",
        }, format="json")
        self.assertEqual(acquired.status_code, 200, acquired.data)
        self.client.force_authenticate(self.doctor)
        reported = self.client.post(f"{record}transition/", {
            "version": 3, "status": "reported", "report": "Recorded test report.",
        }, format="json")
        self.assertEqual(reported.status_code, 200, reported.data)
        queue = self.client.get(f"/api/workforce/handoffs/?visit={self.visit.pk}").data
        self.assertEqual(queue[0]["status"], "returned")
        review = self.post(self.doctor, f"handoffs/{routed.data['id']}/transition/",
                           action="complete", outcome="Reviewed the report.")
        self.assertEqual(review.status_code, 200, review.data)

    def test_external_referral_updates_originating_visit(self):
        owner = self.user("hospital", "receiving")
        destination = Organization.objects.create(
            owner=owner, legal_name="Receiving Hospital", organization_type="hospital", status="verified",
        )
        receiver = self.user("doctor", "receiving")
        StaffMembership.objects.create(user=receiver, role="doctor", organization=destination, status="active")
        routed = self.route("specialist", receiving_facility=destination.pk, specialty="Cardiology")
        self.assertEqual(routed.status_code, 201, routed.data)
        record = f"/api/operations/referrals/{routed.data['referral_route']}/"
        self.client.force_authenticate(receiver)
        self.assertEqual(self.client.get(record).data["specialty"], "Cardiology")
        for version, status in enumerate(("accepted", "in_progress", "completed"), start=1):
            response = self.client.post(f"{record}transition/", {
                "version": version, "status": status, "outcome": "Specialist review complete" if status == "completed" else "",
            }, format="json")
            self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.doctor)
        history = self.client.get(f"/api/workforce/handoffs/?visit={self.visit.pk}").data
        self.assertEqual(history[0]["status"], "returned")
        self.assertEqual(self.client.get(record).data["outcome"], "Specialist review complete")
