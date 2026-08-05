import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from appointments.models import Appointment

from .models import Invoice, Payout

PASSWORD = "testpass123"


def make_user(email, role, first="First", last="Last", **kw):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=role, first_name=first, last_name=last, **kw
    )


class PaymentsApiTests(TestCase):
    def setUp(self):
        self.patient = make_user("patient@example.com", "patient", "Pat", "One")
        self.doctor = make_user("doctor@example.com", "doctor", "Doc", "Two")
        from accounts.models import DoctorProfile

        DoctorProfile.objects.create(user=self.doctor, fees=5000)
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
        self.assertEqual(response.data["patient_name"], "Pat One")
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
            legal_name="HealthPilot Community Hospital",
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


class PayoutWorkflowTests(TestCase):
    def setUp(self):
        from accounts.models import DoctorProfile

        self.patient = make_user("payout-patient@example.com", "patient", "Pat", "Three")
        self.doctor = make_user("payout-doctor@example.com", "doctor", "Doc", "Four")
        self.admin = make_user("payout-admin@example.com", "admin", "Ad", "Min")
        DoctorProfile.objects.create(user=self.doctor, fees=10000)
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date(2030, 2, 1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            status="pending",
        )
        Invoice.objects.create(
            patient=self.patient,
            appointment=self.appointment,
            amount=10000,
            status="paid",
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

    def _withdraw(self, amount=9000):
        self.auth(self.doctor)
        response = self.client.post(
            "/api/payments/withdraw/",
            {
                "amount": amount,
                "method": "bank",
                "account_number": "00112233",
                "account_name": "Doc Four",
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["method"], "bank")
        self.assertEqual(response.data["account_number"], "00112233")
        return response.data["id"]

    def test_approve_then_pay_posts_balanced_ledger_entry(self):
        from communication.models import Notification

        payout_id = self._withdraw()

        self.auth(self.admin)
        response = self.client.get("/api/payments/payouts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["doctor_name"], "Doc Four")

        # cannot pay before approval
        response = self.client.post(
            f"/api/payments/payouts/{payout_id}/action/", {"action": "pay"}
        )
        self.assertEqual(response.status_code, 409)

        response = self.client.post(
            f"/api/payments/payouts/{payout_id}/action/", {"action": "approve"}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "approved")
        self.assertEqual(response.data["processed_by_name"], "Ad Min")

        # an approved payout still reserves the earnings
        self.auth(self.doctor)
        response = self.client.get("/api/payments/earnings/")
        self.assertEqual(response.data["pending"], 0)

        self.auth(self.admin)
        response = self.client.post(
            f"/api/payments/payouts/{payout_id}/action/",
            {"action": "pay", "reference": "BANK-TXN-1"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "paid")
        self.assertEqual(response.data["reference"], "BANK-TXN-1")

        from .models import JournalEntry

        entry = JournalEntry.objects.get(reference=f"PAYOUT-{payout_id}")
        self.assertTrue(entry.is_balanced)
        postings = {p.account.code: (p.direction, p.amount) for p in entry.postings.all()}
        self.assertEqual(
            postings[f"liability:provider:{self.doctor.id}"], ("debit", 9000)
        )
        self.assertEqual(postings["asset:gateway:bank"], ("credit", 9000))

        self.auth(self.doctor)
        response = self.client.get("/api/payments/earnings/")
        self.assertEqual(response.data["paid_out"], 9000)
        self.assertTrue(
            Notification.objects.filter(user=self.doctor, title="Payout paid").exists()
        )

    def test_reject_releases_the_reservation(self):
        payout_id = self._withdraw(amount=4000)

        self.auth(self.doctor)
        response = self.client.get("/api/payments/earnings/")
        self.assertEqual(response.data["pending"], 5000)

        self.auth(self.admin)
        response = self.client.post(
            f"/api/payments/payouts/{payout_id}/action/",
            {"action": "reject", "notes": "Duplicate request"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "rejected")

        self.auth(self.doctor)
        response = self.client.get("/api/payments/earnings/")
        self.assertEqual(response.data["pending"], 9000)

    def test_doctor_cannot_use_admin_payout_endpoints(self):
        payout_id = self._withdraw()
        self.auth(self.doctor)
        response = self.client.get("/api/payments/payouts/")
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            f"/api/payments/payouts/{payout_id}/action/", {"action": "approve"}
        )
        self.assertEqual(response.status_code, 403)


class OrderAndLabPaymentTests(TestCase):
    def setUp(self):
        from services.models import LabOrder, LabTest, Medicine, Order, OrderItem

        self.patient = make_user("order-patient@example.com", "patient", "Olive", "Five")
        self.other_patient = make_user("order-other@example.com", "patient", "Otto", "Six")
        self.pharmacy = make_user("order-pharmacy@example.com", "pharmacy", "City", "Pharmacy")
        self.lab = make_user("order-lab@example.com", "lab", "Med", "Lab")
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy, name="Amoxicillin", price=500, stock=10
        )
        self.order = Order.objects.create(
            patient=self.patient,
            pharmacy=self.pharmacy,
            total=2000,
            delivery=True,
            delivery_fee=1000,
            address="Kampala Rd",
        )
        OrderItem.objects.create(
            order=self.order, medicine=medicine, name=medicine.name, price=500, qty=2
        )
        test = LabTest.objects.create(lab=self.lab, name="CBC", price=5000)
        self.lab_order = LabOrder.objects.create(
            patient=self.patient,
            lab=self.lab,
            test=test,
            status=LabOrder.Status.AWAITING_PAYMENT,
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

    def _pay_via_mock_gateway(self, response):
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["mock"])
        checkout_url = response.data["checkout_url"]
        self.client.credentials()
        response = self.client.post(checkout_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "paid")

    def test_order_paid_end_to_end(self):
        from communication.models import Notification

        self.auth(self.patient)
        response = self.client.post(
            "/api/payments/initiate/",
            {"order_id": self.order.id, "method": "mobile_money"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], 2000)
        invoice_number = response.data["invoice_number"]
        invoice = Invoice.objects.get(number=invoice_number)
        self.assertEqual(invoice.source_type, "order")
        self.assertEqual(invoice.source_id, str(self.order.id))
        # one pharmacy line item plus the delivery fee line
        self.assertEqual(invoice.items.count(), 2)
        self.assertTrue(invoice.items.filter(code="DELIVERY", unit_price=1000).exists())

        self._pay_via_mock_gateway(response)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "confirmed")
        self.assertTrue(
            Notification.objects.filter(user=self.pharmacy, kind="payment").exists()
        )

        # a paid order cannot be paid again
        self.auth(self.patient)
        response = self.client.post(
            "/api/payments/initiate/",
            {"order_id": self.order.id, "method": "mobile_money"},
        )
        self.assertEqual(response.status_code, 409)

    def test_order_ownership_is_enforced(self):
        self.auth(self.other_patient)
        response = self.client.post(
            "/api/payments/initiate/",
            {"order_id": self.order.id, "method": "mobile_money"},
        )
        self.assertEqual(response.status_code, 404)

    def test_lab_order_paid_end_to_end(self):
        self.auth(self.patient)
        response = self.client.post(
            "/api/payments/initiate/",
            {"lab_order_id": self.lab_order.id, "method": "mobile_money"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], 5000)

        self._pay_via_mock_gateway(response)

        self.lab_order.refresh_from_db()
        self.assertEqual(self.lab_order.status, "ready_for_collection")
        invoice = Invoice.objects.get(number=response.data["invoice_number"])
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.source_type, "lab_order")

    def test_initiate_requires_exactly_one_source(self):
        self.auth(self.patient)
        response = self.client.post(
            "/api/payments/initiate/", {"method": "mobile_money"}
        )
        self.assertEqual(response.status_code, 400)


class WalletTests(TestCase):
    def setUp(self):
        from accounts.models import DoctorProfile

        self.patient = make_user("wallet-patient@example.com", "patient", "Wanda", "Seven")
        self.doctor = make_user("wallet-doctor@example.com", "doctor", "Will", "Eight")
        DoctorProfile.objects.create(user=self.doctor, fees=5000)
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date(2030, 3, 1),
            start_time=datetime.time(11, 0),
            end_time=datetime.time(11, 30),
            status="pending",
        )
        self.client = APIClient()
        self.auth()

    def auth(self):
        response = self.client.post(
            "/api/auth/token/", {"email": self.patient.email, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )

    def test_topup_credits_wallet_via_mock_gateway(self):
        from .models import WalletAccount, WalletTransaction

        response = self.client.post(
            "/api/payments/wallet/topup/", {"amount": 20000, "method": "mobile_money"}
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["mock"])

        # not credited before the gateway confirms
        wallet = WalletAccount.objects.get(user=self.patient)
        self.assertEqual(wallet.balance, 0)

        self.client.credentials()
        response = self.client.post(response.data["checkout_url"])
        self.assertEqual(response.status_code, 200)

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 20000)
        self.assertTrue(
            WalletTransaction.objects.filter(
                wallet=wallet, direction="credit", kind="topup", amount=20000
            ).exists()
        )

        self.auth()
        response = self.client.get("/api/payments/wallet/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["balance"], 20000)
        self.assertEqual(len(response.data["transactions"]), 1)

    def test_wallet_payment_and_insufficient_funds(self):
        from .models import WalletAccount
        from .services import credit_wallet
        from .models import WalletTransaction

        credit_wallet(
            user=self.patient,
            amount=8000,
            kind=WalletTransaction.Kind.TOPUP,
            reference="SEED",
        )

        response = self.client.post(
            "/api/payments/initiate/",
            {"appointment_id": self.appointment.id, "method": "wallet"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "paid")
        self.assertEqual(response.data["gateway"], "wallet")

        wallet = WalletAccount.objects.get(user=self.patient)
        self.assertEqual(wallet.balance, 3000)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "confirmed")
        invoice = Invoice.objects.get(number=response.data["invoice_number"])
        self.assertEqual(invoice.status, "paid")
        self.assertTrue(
            invoice.wallet_transactions.filter(direction="debit", kind="payment").exists()
        )

        # remaining balance (3000) cannot cover the next consultation (5000)
        second = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date(2030, 3, 2),
            start_time=datetime.time(11, 0),
            end_time=datetime.time(11, 30),
            status="pending",
        )
        response = self.client.post(
            "/api/payments/initiate/",
            {"appointment_id": second.id, "method": "wallet"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Insufficient wallet balance", response.data["detail"])
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 3000)


class CommissionRuleTests(TestCase):
    def setUp(self):
        from accounts.models import DoctorProfile

        self.patient = make_user("commission-patient@example.com", "patient", "Cleo", "Nine")
        self.doctor = make_user("commission-doctor@example.com", "doctor", "Colin", "Ten")
        self.admin = make_user("commission-admin@example.com", "admin", "Root", "Admin")
        DoctorProfile.objects.create(user=self.doctor, fees=10000)
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date(2030, 4, 1),
            start_time=datetime.time(8, 0),
            end_time=datetime.time(8, 30),
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

    def test_doctor_rule_overrides_default_rate_in_earnings(self):
        from .models import CommissionRule
        from .services import doctor_earnings

        Invoice.objects.create(
            patient=self.patient,
            appointment=self.appointment,
            amount=10000,
            status="paid",
        )
        self.assertEqual(doctor_earnings(self.doctor)["total"], 9000)

        CommissionRule.objects.create(doctor=self.doctor, rate=0.25)
        self.assertEqual(doctor_earnings(self.doctor)["total"], 7500)

    def test_journal_split_uses_doctor_rule(self):
        from .models import CommissionRule, JournalEntry
        from .services import confirm_invoice_payment

        CommissionRule.objects.create(doctor=self.doctor, rate=0.20)
        invoice = Invoice.objects.create(
            patient=self.patient, appointment=self.appointment, amount=10000
        )
        confirm_invoice_payment(invoice=invoice, amount=10000, method="cash")

        entry = JournalEntry.objects.get(reference=f"INVPAID-{invoice.number}")
        self.assertTrue(entry.is_balanced)
        postings = {p.account.code: (p.direction, p.amount) for p in entry.postings.all()}
        self.assertEqual(
            postings[f"liability:provider:{self.doctor.id}"], ("credit", 8000)
        )
        self.assertEqual(
            postings["revenue:platform-commission"], ("credit", 2000)
        )

    def test_organization_rule_applies_without_doctor_rule(self):
        from registry.models import Organization
        from .models import CommissionRule
        from .services import resolve_commission_rate

        organization = Organization.objects.create(
            legal_name="Commission Clinic",
            organization_type="hospital",
            status="verified",
        )
        CommissionRule.objects.create(organization=organization, rate=0.15)
        self.assertEqual(
            resolve_commission_rate(doctor=self.doctor, organization=organization), 0.15
        )
        # a doctor-specific rule is more specific than the organization rule
        CommissionRule.objects.create(doctor=self.doctor, rate=0.05)
        self.assertEqual(
            resolve_commission_rate(doctor=self.doctor, organization=organization), 0.05
        )
        # inactive rules are ignored
        CommissionRule.objects.filter(doctor=self.doctor).update(active=False)
        self.assertEqual(
            resolve_commission_rate(doctor=self.doctor, organization=organization), 0.15
        )

    def test_admin_crud_endpoint(self):
        from .models import CommissionRule

        self.auth(self.admin)
        response = self.client.post(
            "/api/payments/commissions/",
            {"doctor": self.doctor.id, "rate": 0.3},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["doctor_name"], "Colin Ten")

        response = self.client.get("/api/payments/commissions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # a rule must target a doctor or an organization
        response = self.client.post(
            "/api/payments/commissions/", {"rate": 0.3}, format="json"
        )
        self.assertEqual(response.status_code, 400)

        self.auth(self.doctor)
        response = self.client.get("/api/payments/commissions/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(CommissionRule.objects.count(), 1)
