"""Rich demo dataset: populate every section so all pages show real content.

Run from backend/ after seed.py / seed_community.py / seed_workflow.py:
    .venv/bin/python seed_rich_data.py

Idempotent: each section is skipped once its target count is reached.
"""
import datetime as dt
import os
import sys
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

User = get_user_model()
TODAY = timezone.localdate()
NOW = timezone.now()


def users(role):
    return list(User.objects.filter(role=role, is_active=True))


def main():
    from appointments.models import Appointment
    from clinical.models import (
        Allergy, CarePlan, ClinicalEncounter, Condition, MedicationStatement, Observation, Referral,
    )
    from communication.models import Conversation, Message, Notification
    from governance.models import BreakGlassAccess, Consent, PrivilegedAccessGrant
    from registry.models import Organization

    hospital = Organization.objects.filter(organization_type="hospital", status="verified").first()
    patients = users("patient")
    doctors = users("doctor")
    nurse = User.objects.get(email="nurse@healthpilot.test")
    cashier = User.objects.get(email="cashier@healthpilot.test")
    lab = User.objects.get(email="lab@healthpilot.test")
    pharmacy = User.objects.get(email="pharmacy@healthpilot.test")
    insurer = User.objects.get(email="insurance@healthpilot.test")
    hospital_user = User.objects.get(email="hospital@healthpilot.test")
    admin = User.objects.filter(role="admin").first()

    # ------------------------------------------------------------------ clinical record
    if Allergy.objects.count() < 10:
        allergy_data = [("Penicillin", "moderate", "Skin rash"), ("Sulfa drugs", "severe", "Anaphylaxis history"), ("Latex", "mild", "Contact dermatitis"), ("Peanuts", "severe", "Airway swelling"), ("Aspirin", "mild", "Stomach upset"), ("Ibuprofen", "moderate", "Hives"), ("Codeine", "moderate", "Nausea and vomiting"), ("Iodine contrast", "severe", "Bronchospasm"), ("Eggs", "mild", "Oral itching"), ("Dust mites", "mild", "Sneezing")]
        for index, (substance, severity, reaction) in enumerate(allergy_data):
            Allergy.objects.get_or_create(patient=patients[index % len(patients)], substance=substance, defaults={"severity": severity, "reaction": reaction, "recorded_by": doctors[0]})
    if Condition.objects.count() < 10:
        condition_data = [("Essential hypertension", "active"), ("Type 2 diabetes mellitus", "active"), ("Asthma", "active"), ("Peptic ulcer disease", "resolved"), ("Malaria (recurrent)", "resolved"), ("Chronic lower back pain", "active"), ("Iron-deficiency anaemia", "active"), ("Osteoarthritis of knee", "active"), ("Migraine without aura", "active"), ("Allergic rhinitis", "active")]
        for index, (display, status) in enumerate(condition_data):
            Condition.objects.get_or_create(patient=patients[index % len(patients)], display=display, defaults={"clinical_status": status, "recorded_by": doctors[index % len(doctors)], "onset_date": TODAY - dt.timedelta(days=400 + index * 30)})
    if MedicationStatement.objects.count() < 8:
        meds = [("Amlodipine 5 mg", "Once daily"), ("Metformin 850 mg", "Twice daily"), ("Salbutamol inhaler 100 mcg", "As needed"), ("Paracetamol 500 mg", "As needed"), ("Atorvastatin 20 mg", "At night"), ("Omeprazole 20 mg", "Once daily"), ("Losartan 50 mg", "Once daily"), ("Cetirizine 10 mg", "Once daily")]
        for index, (name, freq) in enumerate(meds):
            MedicationStatement.objects.get_or_create(patient=patients[index % len(patients)], medication_name=name, defaults={"dose": "1 unit", "frequency": freq, "status": "active", "recorded_by": doctors[0]})
    if Observation.objects.count() < 12:
        vitals = [("Blood pressure", "124/80", "mmHg"), ("Heart rate", "76", "bpm"), ("Body temperature", "36.8", "°C"), ("Oxygen saturation", "98", "%"), ("Weight", "68", "kg"), ("Height", "165", "cm"), ("Blood pressure", "138/88", "mmHg"), ("Heart rate", "88", "bpm"), ("Body temperature", "38.2", "°C"), ("Respiratory rate", "18", "/min"), ("Weight", "74", "kg"), ("Oxygen saturation", "96", "%")]
        for index, (display, value, unit) in enumerate(vitals):
            Observation.objects.get_or_create(patient=patients[index % len(patients)], display=display, value_text=value, defaults={"category": "vital_sign", "unit": unit, "recorded_by": nurse})
    if CarePlan.objects.count() < 4:
        for index, title in enumerate(["Hypertension management plan", "Diabetes lifestyle programme", "Asthma action plan", "Post-malaria follow-up"]):
            patient = patients[index % len(patients)]
            CarePlan.objects.get_or_create(
                patient=patient, title=title,
                defaults={
                    "author": doctors[index % len(doctors)],
                    "encounter": ClinicalEncounter.objects.filter(patient=patient).first(),
                    "status": "active",
                    "description": "Structured management and review plan.",
                    "goals": "Control symptoms and review in 4 weeks.",
                    "activities": "Medication adherence, diet counselling and scheduled review.",
                    "starts_on": TODAY,
                },
            )

    # ------------------------------------------------------------------ appointments + encounters
    if Appointment.objects.count() < 30:
        for index in range(16):
            patient = patients[index % len(patients)]
            doctor = doctors[index % len(doctors)]
            day_offset = (index % 10) - 5
            status = "completed" if day_offset < -1 else ("confirmed" if day_offset <= 1 else "pending")
            day = TODAY + dt.timedelta(days=day_offset)
            if Appointment.objects.filter(patient=patient, doctor=doctor, date=day).exists():
                continue
            Appointment.objects.create(
                patient=patient, doctor=doctor, booked_by=patient,
                date=day, start_time=dt.time(8 + index % 8, 0), end_time=dt.time(8 + index % 8, 30),
                type="online" if index % 2 else "in_person", status=status,
                reason=["Fever review", "Blood pressure check", "Diabetes follow-up", "Skin rash", "Back pain", "Antenatal review"][index % 6],
            )
    if ClinicalEncounter.objects.count() < 6:
        for appointment in Appointment.objects.filter(status="completed").select_related("patient", "doctor")[:8]:
            ClinicalEncounter.objects.get_or_create(
                appointment=appointment,
                defaults={
                    "patient": appointment.patient, "doctor": appointment.doctor,
                    "status": "signed",
                    "chief_complaint": appointment.reason or "Routine review",
                    "history_of_present_illness": "Symptoms for three days, no red flags.",
                    "examination": "Stable vitals. No acute distress.",
                    "assessment": "Improving on current management.",
                    "treatment_plan": "Continue current medication; review in two weeks.",
                    "safety_net_advice": "Return immediately if symptoms worsen.",
                    "signed_at": NOW,
                },
            )

    # ------------------------------------------------------------------ prescriptions + pharmacy
    from prescriptions.models import Prescription
    from services.models import PharmacyOrder

    if Prescription.objects.count() < 8:
        med_pairs = [("Amoxicillin 500 mg", "1 capsule", "Three times daily", "7 days"), ("Paracetamol 500 mg", "2 tablets", "Every 8 hours", "5 days"), ("Amlodipine 5 mg", "1 tablet", "Once daily", "30 days"), ("Metformin 850 mg", "1 tablet", "Twice daily", "30 days"), ("Cetirizine 10 mg", "1 tablet", "At night", "14 days"), ("Omeprazole 20 mg", "1 capsule", "Before breakfast", "14 days"), ("Azithromycin 250 mg", "2 tablets", "Once daily", "3 days")]
        for index, appointment in enumerate(Appointment.objects.filter(status="completed")[:7]):
            rx_number = f"RX-DEMO-{index + 1:04d}"
            if Prescription.objects.filter(number=rx_number).exists():
                continue
            rx = Prescription.objects.create(number=rx_number, appointment=appointment, doctor=appointment.doctor, patient=appointment.patient, notes="Demo prescription", status="issued")
            name, dose, freq, duration = med_pairs[index % len(med_pairs)]
            rx.items.create(medicine_name=name, dosage=dose, frequency=freq, duration=duration, quantity=21)
            if index < 3:
                PharmacyOrder.objects.get_or_create(pharmacy=pharmacy, prescription_id=rx.id, patient=appointment.patient, defaults={"status": "new"})

    # ------------------------------------------------------------------ laboratory
    from services.models import LabOrder, LabResult, LabTest

    test = LabTest.objects.filter(lab=lab).first()
    if test and LabOrder.objects.count() < 14:
        statuses = ["booked", "sample_collected", "processing", "completed", "booked", "processing"]
        for index, patient in enumerate(patients[:8]):
            if LabOrder.objects.filter(patient=patient, test=test).exists():
                continue
            order = LabOrder.objects.create(patient=patient, lab=lab, test=test, status=statuses[index % len(statuses)], clinical_indication="Demo diagnostic workup", referring_doctor=doctors[index % len(doctors)])
            if order.status == "completed":
                order.result_released = True
                order.result_notes = "Values within reference ranges."
                order.save(update_fields=["result_released", "result_notes"])
                LabResult.objects.get_or_create(order=order, name=test.name, defaults={"value_text": "5.4", "unit": "mmol/L", "interpretation": "normal", "entered_by": lab})

    # ------------------------------------------------------------------ operations
    from operations.models import (
        Admission, AmbulanceDispatch, BedAllocation, ClinicalRound, Complaint, EmergencyCase,
        FacilityBed, ImagingOrder, MaternityEpisode, SurgicalCase, Ward, WardTask,
    )

    ward = Ward.objects.filter(organization=hospital).first()
    if ImagingOrder.objects.count() < 4:
        for index, (modality, study) in enumerate([("xray", "Chest X-Ray PA"), ("ultrasound", "Abdominal ultrasound"), ("ct", "Head CT non-contrast")]):
            ImagingOrder.objects.get_or_create(
                order_number=f"IMG-DEMO-{index + 1:04d}",
                defaults={"organization": hospital, "patient": patients[index], "modality": modality, "study_name": study, "clinical_indication": "Demo imaging workup", "ordering_clinician": doctors[index], "status": ["requested", "scheduled", "completed"][index % 3]},
            )
    if Admission.objects.count() < 3:
        bed = FacilityBed.objects.filter(ward=ward).first()
        for index, patient in enumerate(patients[10:12]):
            admission, created = Admission.objects.get_or_create(
                admission_number=f"ADM-DEMO-{index + 1:04d}",
                defaults={"organization": hospital, "patient": patient, "ward": ward, "reason": ["Pneumonia observation", "Post-operative recovery"][index], "attending_clinician": doctors[index], "status": "admitted"},
            )
            if created and bed:
                BedAllocation.objects.get_or_create(admission=admission, bed=bed, defaults={"assigned_by": nurse})
                WardTask.objects.get_or_create(admission=admission, title="Observations every 4 hours", defaults={"category": "observation", "instructions": "Record full vitals set.", "assigned_to": nurse})
                ClinicalRound.objects.get_or_create(admission=admission, clinician=doctors[index], defaults={"subjective": "Improving", "objective": "Afebrile, vitals stable", "assessment": "Recovering as expected", "plan": "Continue antibiotics; review tomorrow"})
    if SurgicalCase.objects.count() < 3:
        for index, procedure in enumerate(["Appendicectomy", "Hernia repair"]):
            SurgicalCase.objects.get_or_create(
                case_number=f"THR-DEMO-{index + 1:04d}",
                defaults={"organization": hospital, "patient": patients[13 + index], "procedure_name": procedure, "preoperative_diagnosis": "Acute presentation requiring surgery", "surgeon": doctors[2], "scheduled_start": NOW + dt.timedelta(days=index + 1), "status": ["scheduled", "requested"][index % 2]},
            )
    if MaternityEpisode.objects.count() < 3:
        for index in range(2):
            MaternityEpisode.objects.get_or_create(
                episode_number=f"MAT-DEMO-{index + 1:04d}",
                defaults={"organization": hospital, "patient": patients[15 + index], "gravida": 2, "para": 1, "expected_delivery_date": TODAY + dt.timedelta(days=60 + index * 30), "risk_level": ["low", "high"][index], "status": "antenatal"},
            )
    if EmergencyCase.objects.count() < 3:
        for index, complaint in enumerate(["Road traffic accident, limb injury", "Acute asthma attack"]):
            EmergencyCase.objects.get_or_create(
                case_number=f"EMR-DEMO-{index + 1:04d}",
                defaults={"organization": hospital, "patient": patients[17 + index], "chief_complaint": complaint, "acuity": ["urgent", "emergent"][index], "status": ["triaged", "in_treatment"][index]},
            )
    if AmbulanceDispatch.objects.count() < 2:
        AmbulanceDispatch.objects.get_or_create(
            dispatch_number="AMB-DEMO-0002",
            defaults={"organization": hospital, "caller_name": "Demo Caller", "caller_phone": "+256 700 000 111", "pickup_location": "Busiika town centre", "destination": "Hope Medical Centre", "status": "en_route"},
        )
    if Complaint.objects.count() < 2:
        Complaint.objects.get_or_create(complainant=patients[4], defaults={"category": "service", "description": "Long waiting time at the outpatient desk.", "status": "open"})

    # ------------------------------------------------------------------ payments & finance
    from payments.models import (
        ApprovalLimit, CommissionRule, DepartmentBudget, Expense, FinancialPeriod,
        Invoice, PaymentTransaction, Payout, Receipt, RefundRequest, Subscription,
        WalletAccount, WalletTransaction,
    )

    if Invoice.objects.count() < 10:
        for index, patient in enumerate(patients[:8]):
            number = f"INV-DEMO-{index + 1:05d}"
            if Invoice.objects.filter(number=number).exists():
                continue
            amount = [25000, 45000, 60000, 15000, 90000, 30000, 55000, 40000][index]
            status = ["paid", "paid", "pending", "partially_paid", "paid", "pending", "paid", "pending"][index]
            invoice = Invoice.objects.create(number=number, patient=patient, amount=amount, status=status, organization=hospital)
            if status in {"paid", "partially_paid"}:
                paid_amount = amount if status == "paid" else amount // 2
                txn = PaymentTransaction.objects.create(number=f"PAY-DEMO-{index + 1:05d}", invoice=invoice, amount=paid_amount, method="cash", status="confirmed", received_by=cashier, confirmed_at=NOW)
                Receipt.objects.get_or_create(payment=txn, defaults={"issued_by": cashier})
                if status == "paid":
                    invoice.paid_at = NOW
                    invoice.save(update_fields=["paid_at"])
    if WalletAccount.objects.count() < 3:
        for index, patient in enumerate(patients[:4]):
            balance = [120000, 45000, 200000, 60000][index]
            account, created = WalletAccount.objects.get_or_create(user=patient, defaults={"balance": balance})
            if created:
                WalletTransaction.objects.create(wallet=account, direction="credit", kind="topup", amount=balance, reference=f"TOPUP-DEMO-{index + 1}")
    if Payout.objects.count() < 2:
        for index, doctor in enumerate(doctors[:2]):
            Payout.objects.get_or_create(doctor=doctor, amount=150000 + index * 50000, defaults={"status": ["paid", "pending"][index], "reference": f"PAYOUT-DEMO-{index + 1}"})
    paid_txn = PaymentTransaction.objects.filter(status="confirmed").first()
    if paid_txn and not RefundRequest.objects.exists():
        RefundRequest.objects.create(number="RFD-DEMO-0001", payment=paid_txn, amount=min(10000, paid_txn.amount), reason="Patient overpaid at the counter.", requested_by=cashier, status="requested")
    if not Expense.objects.exists():
        Expense.objects.create(number="EXP-DEMO-0001", organization=hospital, description="Surgical consumables restock", amount=450000, category="medical_supplies", incurred_on=TODAY, requested_by=cashier, status="approved")
        Expense.objects.create(number="EXP-DEMO-0002", organization=hospital, description="Generator fuel", amount=180000, category="utilities", incurred_on=TODAY - dt.timedelta(days=2), requested_by=cashier, status="submitted")
    if not FinancialPeriod.objects.exists():
        period = FinancialPeriod.objects.create(organization=hospital, name=f"FY {TODAY.year}", starts_on=dt.date(TODAY.year, 1, 1), ends_on=dt.date(TODAY.year, 12, 31), status="open", created_by=admin)
    else:
        period = FinancialPeriod.objects.first()
    if period and not DepartmentBudget.objects.exists():
        from workforce.models import Department
        for dept in Department.objects.filter(organization=hospital)[:2]:
            DepartmentBudget.objects.get_or_create(organization=hospital, period=period, department=dept, defaults={"amount": 5000000, "notes": "Demo allocation"})
    if not ApprovalLimit.objects.exists():
        ApprovalLimit.objects.create(organization=hospital, role_code="cashier", maximum_amount=500000)
        ApprovalLimit.objects.create(organization=hospital, role_code="finance_manager", maximum_amount=10000000)
    if not CommissionRule.objects.exists():
        CommissionRule.objects.create(rate=Decimal("10.00"), organization=hospital)
    if not Subscription.objects.exists():
        Subscription.objects.create(user=hospital_user, plan="premium", active=True, started_at=NOW - dt.timedelta(days=90), expires_at=NOW + dt.timedelta(days=275))

    # ------------------------------------------------------------------ insurance
    from services.models import InsuranceClaim, InsurancePolicy, InsurancePreauthorization, PatientCoverage

    gold = InsurancePolicy.objects.filter(provider=insurer).first()
    if InsurancePolicy.objects.count() < 4:
        InsurancePolicy.objects.get_or_create(provider=insurer, name="Silver Family Plan", defaults={"coverage_percent": 70, "premium": 35000, "description": "Family outpatient cover"})
        InsurancePolicy.objects.get_or_create(provider=insurer, name="Bronze Individual", defaults={"coverage_percent": 50, "premium": 15000, "description": "Basic individual cover"})
    if gold and PatientCoverage.objects.count() < 5:
        for index, patient in enumerate(patients[:5]):
            PatientCoverage.objects.get_or_create(patient=patient, provider=insurer, member_id=f"MEM-DEMO-{index + 2:04d}", defaults={"policy": gold})
    if gold and InsuranceClaim.objects.count() < 4:
        for index, coverage in enumerate(PatientCoverage.objects.filter(provider=insurer)[:3]):
            if InsuranceClaim.objects.filter(coverage=coverage).exists():
                continue
            InsuranceClaim.objects.create(patient=coverage.patient, provider=insurer, policy=gold, coverage=coverage, amount=45000 + index * 20000, status=["submitted", "under_review", "approved"][index % 3], requested_by=coverage.patient)
    if gold and not InsurancePreauthorization.objects.filter(status="approved").exists():
        coverage = PatientCoverage.objects.filter(provider=insurer).first()
        if coverage:
            InsurancePreauthorization.objects.create(patient=coverage.patient, provider=insurer, policy=gold, coverage=coverage, service_name="Elective surgery", clinical_indication="Planned hernia repair", requested_amount=350000, status="approved", requesting_facility=hospital_user)

    # ------------------------------------------------------------------ reviews & referrals
    from reviews.models import Review

    if Review.objects.count() < 6:
        for index, appointment in enumerate(Appointment.objects.filter(status="completed")[:8]):
            Review.objects.get_or_create(appointment=appointment, defaults={"patient": appointment.patient, "doctor": appointment.doctor, "rating": [5, 4, 5, 3, 4, 5, 4, 5][index], "comment": ["Very attentive doctor.", "Quick and professional.", "Explained everything clearly.", "Long wait but good care.", "Highly recommended.", "Thorough examination.", "Good follow-up advice.", "Friendly and calm."][index]})
    if Referral.objects.count() < 4:
        for index, patient in enumerate(patients[5:9]):
            Referral.objects.get_or_create(
                patient=patient, referring_provider=doctors[index], target_specialty=["Cardiology", "Orthopaedics", "ENT Surgery"][index % 3],
                defaults={"reason": ["Murmur on examination", "Persistent knee pain", "Recurrent sinusitis"][index % 3], "target_provider": doctors[(index + 4) % len(doctors)], "status": ["sent", "accepted", "completed"][index % 3], "priority": "routine"},
            )

    # ------------------------------------------------------------------ communication
    if Conversation.objects.count() < 5:
        for index, patient in enumerate(patients[:4]):
            doctor = doctors[index % len(doctors)]
            conversation, created = Conversation.objects.get_or_create(patient=patient, doctor=doctor)
            if created:
                Message.objects.create(conversation=conversation, sender=patient, text="Hello doctor, I would like to follow up on my results.")
                Message.objects.create(conversation=conversation, sender=doctor, text="Hello, your results are ready. Everything looks stable — see your health record.")
    if Notification.objects.count() < 60:
        from communication.services import notify
        for user in [nurse, cashier, lab, pharmacy, insurer, hospital_user, *doctors[:5], *patients[:8]]:
            notify(user, "Welcome to your workspace", "Your dashboard is now populated with live demonstration activity.", kind="general")

    # ------------------------------------------------------------------ journeys operational layer
    from journeys.models import (
        CallCentreCallback, CareConference, ClinicalTask, GeneratedClinicalDocument,
        MedicationAdherenceEntry, MedicationRenewalRequest, OperationalAction,
        QueueTicket, ResultReview, WaitingRoomEntry, WorkflowCase,
    )

    case = WorkflowCase.objects.first()
    if not case:
        case = WorkflowCase.objects.create(reference="WFC-DEMO-0001", page_slug="feedback-complaint", title="Demo workflow case", status="open", patient=patients[0])
    if QueueTicket.objects.count() < 3:
        for index, patient in enumerate(patients[:3]):
            QueueTicket.objects.get_or_create(number=f"Q-{index + 101}", organization=hospital, patient=patient, defaults={"status": ["waiting", "called", "served"][index % 3], "counter": f"Desk {index + 1}"})
    if WaitingRoomEntry.objects.count() < 2:
        for appointment in Appointment.objects.filter(status="confirmed", date=TODAY)[:2]:
            WaitingRoomEntry.objects.get_or_create(appointment=appointment, patient=appointment.patient, defaults={"organization": hospital, "status": "waiting", "checked_in_at": NOW})
    lab_result = LabResult.objects.first()
    if lab_result and not ResultReview.objects.exists():
        ResultReview.objects.create(result_type="laboratory", result_id=lab_result.id, patient=lab_result.order.patient, reviewer=doctors[0], action="acknowledged", note="Reviewed and discussed with patient.")
    if not CareConference.objects.exists():
        CareConference.objects.create(workflow_case=case, patient=patients[5], organization=hospital, title="Complex care review — hypertension and diabetes", scheduled_at=NOW + dt.timedelta(days=2), agenda="Medication optimisation and lifestyle plan.", chair=doctors[0])
    if not ClinicalTask.objects.exists():
        ClinicalTask.objects.create(workflow_case=case, patient=patients[5], task_type="follow_up", instructions="Repeat blood pressure check in one week.", assigned_to=nurse, due_at=NOW + dt.timedelta(days=7), created_by=doctors[0])
    rx = Prescription.objects.first()
    if rx and not MedicationRenewalRequest.objects.exists():
        MedicationRenewalRequest.objects.create(workflow_case=case, prescription=rx, patient=rx.patient, prescriber=rx.doctor, reason="Stable on current dose; requesting repeat supply.")
    if rx and not MedicationAdherenceEntry.objects.exists():
        MedicationAdherenceEntry.objects.create(workflow_case=case, patient=rx.patient, prescription=rx, scheduled_for=NOW - dt.timedelta(hours=4), status="taken", taken_at=NOW - dt.timedelta(hours=4))
        MedicationAdherenceEntry.objects.create(workflow_case=case, patient=rx.patient, prescription=rx, scheduled_for=NOW + dt.timedelta(hours=4), status="scheduled")
    if not CallCentreCallback.objects.exists():
        CallCentreCallback.objects.create(workflow_case=case, patient=patients[6], phone=patients[6].phone or "+256 700 123 456", reason="Post-discharge follow-up call", scheduled_for=NOW + dt.timedelta(days=1))
    if not GeneratedClinicalDocument.objects.exists():
        GeneratedClinicalDocument.objects.create(verification_code="DOC-DEMO-0001", document_type="sick_note", title="Sick leave note", patient=patients[7], organization=hospital, created_by=doctors[0], content={"days": 3, "reason": "Acute illness"})
    if not OperationalAction.objects.exists():
        OperationalAction.objects.create(workflow_case=case, page_slug="patient-arrival-board", domain="front_desk", operation_code="check_in", created_by=nurse, patient=patients[0], state="completed", organization=hospital)

    # ------------------------------------------------------------------ governance
    if Consent.objects.count() < 6:
        for index, patient in enumerate(patients[:6]):
            Consent.objects.get_or_create(patient=patient, granted_to=doctors[index % len(doctors)], consent_type="treatment", purpose="treatment", defaults={"data_categories": ["patient_summary", "consultation_record"]})
    if not BreakGlassAccess.objects.exists():
        BreakGlassAccess.objects.create(requester=doctors[1], patient=patients[9], reason="Emergency access during unconscious presentation", status="active", started_at=NOW, expires_at=NOW + dt.timedelta(hours=4))
    if not PrivilegedAccessGrant.objects.exists():
        PrivilegedAccessGrant.objects.create(requester=admin, patient=patients[11], purpose="audit", reason="Record completeness audit for quality review.", scopes=["read_only"], status="active", expires_at=NOW + dt.timedelta(days=1))

    # ------------------------------------------------------------------ enterprise extras
    from enterprise.models import MasterPatientIndex, PatientMerge, ReportRun, RoleContext, RoleDelegation, SavedReport

    mpis = list(MasterPatientIndex.objects.all()[:2])
    if len(mpis) == 2 and not PatientMerge.objects.exists():
        PatientMerge.objects.create(survivor=mpis[0], duplicate=mpis[1], reason="Duplicate registration at reception; same national ID.", status="proposed", requested_by=User.objects.filter(role="records_officer").first())
    saved_report = SavedReport.objects.first()
    if saved_report and not ReportRun.objects.exists():
        ReportRun.objects.create(report=saved_report, status="completed", completed_at=NOW, result={"rows": 42, "note": "Demo report run"}, requested_by=admin)
    contexts = list(RoleContext.objects.filter(user=nurse)[:2])
    if len(contexts) == 2 and not RoleDelegation.objects.exists():
        RoleDelegation.objects.create(delegator_context=contexts[0], delegatee_context=contexts[1], reason="Weekend cover delegation", starts_at=NOW, ends_at=NOW + dt.timedelta(days=3), permissions=["view_ward_board"])

    # ------------------------------------------------------------------ workforce extras
    from workforce.models import MedicationAdministration, NursingNote, PatientVisit, StaffInvitation

    visit = PatientVisit.objects.exclude(status__in=["completed", "cancelled"]).first()
    if visit and not MedicationAdministration.objects.exists():
        MedicationAdministration.objects.create(visit=visit, nurse=nurse, medication="Paracetamol 500 mg", dose="1 g PO", administered_at=NOW, status="administered", notes="First dose tolerated well.")
    if visit and NursingNote.objects.count() < 3:
        NursingNote.objects.create(visit=visit, nurse=nurse, note="Patient comfortable, observations stable.")
        NursingNote.objects.create(visit=visit, nurse=nurse, note="Encouraged oral fluids; next observations due in 4 hours.")
    if not StaffInvitation.objects.exists():
        import uuid

        manager = User.objects.filter(email="manager@healthpilot.test").first()
        StaffInvitation.objects.create(token=uuid.uuid4(), organization=hospital, email="new.nurse@healthpilot.test", role="nurse", invited_by=manager, expires_at=NOW + dt.timedelta(days=14))

    print("Rich demo data complete.")


if __name__ == "__main__":
    main()
