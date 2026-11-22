import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import DoctorProfile, User
from appointments.models import Appointment

from .models import Invoice, Payout

PASSWORD = "testpass123"


def make_user(email, role, first="First", last="Last"):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=role, first_name=first, last_name=last
    )


class PaymentsApiTests(TestCase):
    def setUp(self):
        self.patient = make_user("patient@example.com", "patient", "Pat", "One")
        self.doctor = make_user("doctor@example.com", "doctor", "Doc", "Two")
        DoctorProfile.objects.update_or_create(user=self.doctor, defaults={"fees": 20000})
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date(2030, 1, 1),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 30),
            status="pending",
        )
        self.client = APIClient()

    def auth(self, user):
        response = self.client.post(
            "/api/auth/token/", {"email": user.email, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )

    def test_initiate_then_mock_webhook_pays_and_confirms(self):
        self.auth(self.patient)
        response = self.client.post(
            "/api/payments/initiate/",
            {"appointment_id": self.appointment.id, "method": "mobile_money"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["mock"])
        self.assertTrue(response.data["invoice_number"].startswith("INV-"))
        invoice_number = response.data["invoice_number"]
        checkout_url = response.data["checkout_url"]

        # webhook is AllowAny
        self.client.credentials()
        response = self.client.post(checkout_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "paid")

        invoice = Invoice.objects.get(number=invoice_number)
        self.assertEqual(invoice.status, "paid")
        self.assertIsNotNone(invoice.paid_at)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "confirmed")

        # both parties notified
        from communication.models import Notification

        self.assertTrue(
            Notification.objects.filter(user=self.patient, kind="payment").exists()
        )
        self.assertTrue(
            Notification.objects.filter(user=self.doctor, kind="payment").exists()
        )

    def test_invoices_list_and_receipt(self):
        invoice = Invoice.objects.create(
            patient=self.patient, appointment=self.appointment, amount=5000
        )
        self.auth(self.patient)
        response = self.client.get("/api/payments/invoices/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["number"], invoice.number)
        self.assertEqual(
            response.data[0]["appointment_info"]["doctor_name"], "Doc Two"
        )

        response = self.client.get(f"/api/payments/invoices/{invoice.id}/receipt/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["number"], invoice.number)
        self.assertEqual(response.data["patient"], "Pat One")
        self.assertEqual(response.data["doctor"], "Doc Two")

        # doctor also sees the invoice
        self.auth(self.doctor)
        response = self.client.get("/api/payments/invoices/")
        self.assertEqual(len(response.data), 1)

    def test_withdraw_validation_and_earnings(self):
        self.auth(self.doctor)
        # no earnings yet -> reject
        response = self.client.post("/api/payments/withdraw/", {"amount": 100})
        self.assertEqual(response.status_code, 400)

        # paid invoice of 10000 -> earnings 9000 after 10% commission
        Invoice.objects.create(
            patient=self.patient,
            appointment=self.appointment,
            amount=10000,
            status="paid",
        )
        response = self.client.get("/api/payments/earnings/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 9000)
        self.assertEqual(response.data["pending"], 9000)
        self.assertEqual(response.data["paid_out"], 0)

        response = self.client.post("/api/payments/withdraw/", {"amount": 9500})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/payments/withdraw/", {"amount": 4000})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")
        self.assertTrue(
            Payout.objects.filter(doctor=self.doctor, amount=4000).exists()
        )

        # pending payout reserves funds
        response = self.client.get("/api/payments/earnings/")
        self.assertEqual(response.data["pending"], 5000)
        self.assertEqual(len(response.data["payouts"]), 1)


class FacilityBillingWorkflowTests(TestCase):
    def setUp(self):
        from registry.models import Organization
        from workforce.models import StaffMembership

        self.patient = make_user("billing-patient@example.com", "patient", "Billing", "Patient")
        self.cashier = make_user("cashier@example.com", "cashier", "Cash", "Officer")
        self.manager = make_user(
            "facility-manager@example.com", "facility_manager", "Facility", "Manager"
        )
        self.organization = Organization.objects.create(
            legal_name="MyDoctor Community Hospital",
            organization_type=Organization.Type.HOSPITAL,
            license_number="HOSP-BILL-001",
            status=Organization.Status.VERIFIED,
            active=True,
        )
        StaffMembership.objects.create(
            user=self.cashier,
            organization=self.organization,
            role="cashier",
            status=StaffMembership.Status.ACTIVE,
            is_primary=True,
        )
        StaffMembership.objects.create(
            user=self.manager,
            organization=self.organization,
            role="facility_manager",
            status=StaffMembership.Status.ACTIVE,
            is_primary=True,
        )
        self.client = APIClient()

    def test_itemized_invoice_partial_payment_receipts_and_shift_close(self):
        self.client.force_authenticate(self.cashier)
        shift_response = self.client.post(
            "/api/billing/shifts/",
            {"opening_float": 10000},
            format="json",
        )
        self.assertEqual(shift_response.status_code, 201, shift_response.data)
        shift_id = shift_response.data["id"]

        invoice_response = self.client.post(
            "/api/billing/invoices/",
            {
                "patient": self.patient.id,
                "discount_amount": 5000,
                "items": [
                    {
                        "code": "CONSULT",
                        "description": "Outpatient consultation",
                        "quantity": "1.00",
                        "unit_price": 30000,
                    },
                    {
                        "code": "CBC",
                        "description": "Complete blood count",
                        "quantity": "1.00",
                        "unit_price": 20000,
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(invoice_response.status_code, 201, invoice_response.data)
        self.assertEqual(invoice_response.data["amount"], 45000)
        invoice_id = invoice_response.data["id"]

        partial = self.client.post(
            f"/api/billing/invoices/{invoice_id}/payments/",
            {"amount": 20000, "method": "cash"},
            format="json",
        )
        self.assertEqual(partial.status_code, 201, partial.data)
        self.assertEqual(partial.data["invoice"]["status"], "partially_paid")
        self.assertEqual(partial.data["invoice"]["balance"], 25000)
        self.assertTrue(partial.data["receipt"]["number"].startswith("RCT-"))

        final = self.client.post(
            f"/api/billing/invoices/{invoice_id}/payments/",
            {
                "amount": 25000,
                "method": "mobile_money",
                "reference": "MM-12345",
            },
            format="json",
        )
        self.assertEqual(final.status_code, 201, final.data)
        self.assertEqual(final.data["invoice"]["status"], "paid")
        self.assertEqual(final.data["invoice"]["balance"], 0)

        receipt_id = final.data["receipt"]["id"]
        receipt = self.client.get(f"/api/payments/receipts/{receipt_id}/")
        self.assertEqual(receipt.status_code, 200, receipt.data)
        self.assertEqual(receipt.data["invoice_number"], final.data["invoice"]["number"])
        self.assertEqual(len(receipt.data["items"]), 2)

        close = self.client.post(
            f"/api/billing/shifts/{shift_id}/close/",
            {"closing_cash": 30000},
            format="json",
        )
        self.assertEqual(close.status_code, 200, close.data)
        self.assertEqual(close.data["expected_cash"], 30000)
        self.assertEqual(close.data["variance"], 0)
        self.assertEqual(close.data["status"], "closed")

    def test_patient_cannot_issue_facility_invoice(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/billing/invoices/",
            {
                "patient": self.patient.id,
                "organization": self.organization.id,
                "items": [
                    {
                        "description": "Consultation",
                        "quantity": "1.00",
                        "unit_price": 10000,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_facility_manager_has_billing_oversight_without_cashier_authority(self):
        invoice = Invoice.objects.create(
            patient=self.patient,
            organization=self.organization,
            amount=25000,
            status=Invoice.Status.PENDING,
        )
        self.client.force_authenticate(self.manager)

        summary = self.client.get("/api/billing/summary/")
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertEqual(summary.data["pending_invoices"], 1)

        invoices = self.client.get("/api/billing/invoices/")
        self.assertEqual(invoices.status_code, 200, invoices.data)
        self.assertEqual(len(invoices.data), 1)

        issue = self.client.post(
            "/api/billing/invoices/",
            {
                "patient": self.patient.id,
                "items": [
                    {
                        "description": "Consultation",
                        "quantity": "1.00",
                        "unit_price": 10000,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(issue.status_code, 403)

        collect = self.client.post(
            f"/api/billing/invoices/{invoice.id}/payments/",
            {"amount": 10000, "method": "cash"},
            format="json",
        )
        self.assertEqual(collect.status_code, 403)

        open_shift = self.client.post(
            "/api/billing/shifts/", {"opening_float": 10000}, format="json"
        )
        self.assertEqual(open_shift.status_code, 403)
