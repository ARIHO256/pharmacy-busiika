"""Populate the owner's personal accounts with live demo data.

Covers:
  * arihonowaman05@gmail.com — patient portal (appointments, encounters, Rx,
    labs, orders, invoices, wallet, insurance, conversations, health record)
  * arihonowaman@gmail.com — Bugema pharmacy portal (catalog, orders, alerts)

Run from backend/:
    .venv/bin/python seed_my_account.py
"""
import datetime as dt
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

User = get_user_model()
TODAY = timezone.localdate()
NOW = timezone.now()
PATIENT_EMAIL = "arihonowaman05@gmail.com"
PHARMACY_EMAIL = "arihonowaman@gmail.com"


def main():
    from appointments.models import Appointment
    from clinical.models import Allergy, ClinicalEncounter, Condition, MedicationStatement, Observation
    from communication.models import Conversation, Message
    from communication.services import notify
    from prescriptions.models import Prescription
    from registry.models import Organization
    from services.models import LabOrder, LabResult, LabTest, Medicine, Order, OrderItem, PatientCoverage, InsurancePolicy

    me = User.objects.get(email=PATIENT_EMAIL)
    pharmacy_user = User.objects.get(email=PHARMACY_EMAIL)
    bugema = Organization.objects.get(pk=5)
    hospital = Organization.objects.filter(organization_type="hospital", status="verified").first()
    doctor = User.objects.get(email="dr.nakato@healthpilot.test")
    doctor2 = User.objects.get(email="dr.tumusiime@healthpilot.test")
    lab = User.objects.get(email="lab@healthpilot.test")
    insurer = User.objects.get(email="insurance@healthpilot.test")
    cashier = User.objects.get(email="cashier@healthpilot.test")

    # ------------------------------------------------ patient: appointments + encounter + rx
    completed, _ = Appointment.objects.get_or_create(
        patient=me, doctor=doctor, date=TODAY - dt.timedelta(days=6), start_time=dt.time(9, 0),
        defaults={"end_time": dt.time(9, 30), "type": "in_person", "status": "completed", "reason": "Fever and headache", "booked_by": me},
    )
    encounter, _ = ClinicalEncounter.objects.get_or_create(
        appointment=completed,
        defaults={"patient": me, "doctor": doctor, "status": "signed", "chief_complaint": "Fever and headache",
                  "history_of_present_illness": "Three days of fever with frontal headache.",
                  "examination": "Temp 38.1°C, mild pharyngeal injection.", "assessment": "Viral upper respiratory infection; malaria ruled out.",
                  "treatment_plan": "Paracetamol and fluids; review if fever persists beyond 48 hours.",
                  "safety_net_advice": "Return immediately for stiff neck, confusion or persistent vomiting.",
                  "signed_at": NOW - dt.timedelta(days=6)},
    )
    rx, rx_created = Prescription.objects.get_or_create(
        number="RX-MY-0001",
        defaults={"appointment": completed, "doctor": doctor, "patient": me, "notes": "Take with food.", "status": "issued"},
    )
    if rx_created:
        rx.items.create(medicine_name="Paracetamol 500 mg", dosage="2 tablets", frequency="Every 8 hours", duration="3 days", quantity=18)
    upcoming_specs = [
        (doctor2, 2, "confirmed", "Cardiology review", "online"),
        (doctor, 9, "pending", "Follow-up consultation", "in_person"),
    ]
    for doc, offset, status, reason, kind in upcoming_specs:
        Appointment.objects.get_or_create(
            patient=me, doctor=doc, date=TODAY + dt.timedelta(days=offset), start_time=dt.time(10, 0),
            defaults={"end_time": dt.time(10, 30), "type": kind, "status": status, "reason": reason, "booked_by": me},
        )

    # ------------------------------------------------ patient: health record
    Allergy.objects.get_or_create(patient=me, substance="Penicillin", defaults={"severity": "moderate", "reaction": "Skin rash", "recorded_by": doctor})
    Condition.objects.get_or_create(patient=me, display="Recurrent migraine", defaults={"clinical_status": "active", "recorded_by": doctor, "onset_date": TODAY - dt.timedelta(days=300)})
    MedicationStatement.objects.get_or_create(patient=me, medication_name="Sumatriptan 50 mg", defaults={"dose": "1 tablet", "frequency": "At migraine onset", "status": "active", "recorded_by": doctor})
    for display, value, unit in [("Blood pressure", "121/79", "mmHg"), ("Heart rate", "72", "bpm"), ("Weight", "71", "kg")]:
        Observation.objects.get_or_create(patient=me, display=display, value_text=value, defaults={"category": "vital_sign", "unit": unit, "recorded_by": doctor})

    # ------------------------------------------------ patient: lab
    test = LabTest.objects.filter(lab=lab).first()
    if test and not LabOrder.objects.filter(patient=me).exists():
        order = LabOrder.objects.create(patient=me, lab=lab, test=test, status="completed", clinical_indication="Fever workup", referring_doctor=doctor, result_released=True, result_notes="Within reference ranges.")
        LabResult.objects.create(order=order, name=test.name, value_text="Negative", interpretation="normal", entered_by=lab)

    # ------------------------------------------------ patient: store order + invoices + wallet
    from payments.models import Invoice, PaymentTransaction, Receipt, WalletAccount, WalletTransaction

    med = Medicine.objects.filter(pharmacy__email="pharmacy@healthpilot.test").first()
    if med and not Order.objects.filter(patient=me).exists():
        order = Order.objects.create(patient=me, pharmacy=med.pharmacy, total=med.price * 2, status="confirmed")
        OrderItem.objects.create(order=order, medicine=med, name=med.name, price=med.price, qty=2)
    inv_paid, inv_created = Invoice.objects.get_or_create(
        number="INV-MY-0001",
        defaults={"patient": me, "amount": 30000, "status": "paid", "organization": hospital, "appointment": completed, "paid_at": NOW - dt.timedelta(days=6)},
    )
    if inv_created:
        txn = PaymentTransaction.objects.create(number="PAY-MY-0001", invoice=inv_paid, amount=30000, method="mobile_money", status="confirmed", confirmed_at=NOW - dt.timedelta(days=6))
        Receipt.objects.get_or_create(payment=txn, defaults={"issued_by": cashier})
    Invoice.objects.get_or_create(number="INV-MY-0002", defaults={"patient": me, "amount": 80000, "status": "pending", "organization": hospital})
    wallet, wallet_created = WalletAccount.objects.get_or_create(user=me, defaults={"balance": 150000})
    if wallet_created:
        WalletTransaction.objects.create(wallet=wallet, direction="credit", kind="topup", amount=150000, reference="TOPUP-MY-0001")

    # ------------------------------------------------ patient: insurance
    gold = InsurancePolicy.objects.filter(provider=insurer).first()
    if gold:
        PatientCoverage.objects.get_or_create(patient=me, provider=insurer, member_id="MEM-MY-0001", defaults={"policy": gold})

    # ------------------------------------------------ patient: conversation + notifications
    conversation, convo_created = Conversation.objects.get_or_create(patient=me, doctor=doctor)
    if convo_created:
        Message.objects.create(conversation=conversation, sender=me, text="Hello Dr. Nakato, the fever has settled. Should I finish the tablets?")
        Message.objects.create(conversation=conversation, sender=doctor, text="Great progress — yes, complete the full course and hydrate well.")
        Message.objects.create(conversation=conversation, sender=me, text="Noted, thank you doctor.")
    notify(me, "Your record is up to date", "Recent visit notes, results and prescriptions are in your health record.", kind="general", action_url="/patient/health-record")
    notify(me, "Upcoming appointment", f"Cardiology review with {doctor2.display_name} on {TODAY + dt.timedelta(days=2)} at 10:00.", kind="reminder", action_url="/patient/appointments")

    # ------------------------------------------------ pharmacy owner: catalog + orders + alerts
    catalog = [
        ("Paracetamol 500 mg (20 tablets)", "Pain and fever relief", 3000, 200),
        ("Amoxicillin 250 mg (10 capsules)", "Prescription antibiotic", 8500, 90),
        ("Cetirizine 10 mg (10 tablets)", "Allergy relief", 4500, 150),
        ("Omeprazole 20 mg (14 capsules)", "Acid reflux treatment", 9800, 70),
        ("ORS sachets (5 pack)", "Oral rehydration salts", 2500, 180),
        ("Digital Thermometer", "Fast-read clinical thermometer", 22000, 35),
    ]
    for name, description, price, stock in catalog:
        Medicine.objects.get_or_create(pharmacy=pharmacy_user, name=name, defaults={"description": description, "price": price, "stock": stock})
    my_med = Medicine.objects.filter(pharmacy=pharmacy_user).first()
    if my_med and not Order.objects.filter(pharmacy=pharmacy_user).exists():
        buyer = User.objects.get(email="patient3@healthpilot.test")
        order = Order.objects.create(patient=buyer, pharmacy=pharmacy_user, total=my_med.price * 3, status="pending")
        OrderItem.objects.create(order=order, medicine=my_med, name=my_med.name, price=my_med.price, qty=3)
    notify(pharmacy_user, "New store order", "A patient placed an order with Bugema — confirm and prepare it.", kind="pharmacy", action_url="/pharmacy/orders")
    notify(pharmacy_user, "Your pharmacy is verified", "Bugema is live in the provider directory and can receive orders.", kind="general")

    print("Personal account seeding complete.")


if __name__ == "__main__":
    main()
