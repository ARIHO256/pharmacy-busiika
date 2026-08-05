"""Role-scoped operational data for deep pages.

Unlike the original page catalogue, these loaders query canonical domain models.
Every page resolves to a canonical domain dataset, a schema-backed enterprise
record set, an operational-action ledger, or an explicitly labelled work queue.
No page silently falls back to fabricated metrics or an unconfigured shell.
"""

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.permissions import request_role
from enterprise.access import (
    active_context_for, active_organization, active_role, is_platform_super_admin,
    record_queryset_for,
)
from .definitions import definition_for


def _iso(value):
    return value.isoformat() if value else None


def _user(user):
    if not user:
        return None
    return {"id": user.id, "name": user.display_name, "email": user.email, "phone": user.phone}



def _active_role_label(user):
    return active_role(user)


def _mpi(record):
    if not record:
        return None
    patient = getattr(record, "patient", None)
    return {
        "id": record.id,
        "enterprise_id": str(getattr(record, "enterprise_id", "")),
        "patient": _user(patient),
        "normalized_name": getattr(record, "normalized_name", ""),
        "normalized_phone": getattr(record, "normalized_phone", ""),
        "date_of_birth": str(getattr(record, "date_of_birth", "") or ""),
        "national_identifier": getattr(record, "national_identifier", ""),
        "status": getattr(record, "status", ""),
        "confidence_score": getattr(record, "confidence_score", None),
    }


def _current_bed(admission):
    allocation = admission.bed_allocations.filter(released_at__isnull=True).select_related("bed").first()
    bed = allocation.bed if allocation else None
    return {
        "id": getattr(bed, "id", None),
        "label": getattr(bed, "label", None),
        "status": getattr(bed, "status", None),
    } if bed else None


def _appointment(row):
    return {
        "id": row.id,
        "patient": _user(row.patient),
        "provider": _user(row.doctor),
        "date": str(row.date),
        "start_time": str(row.start_time),
        "end_time": str(row.end_time),
        "type": row.type,
        "type_label": row.get_type_display(),
        "status": row.status,
        "status_label": row.get_status_display(),
        "reason": row.reason,
        "meeting_link": getattr(row, "meeting_link", ""),
    }


def _invoice(row):
    return {
        "id": row.id,
        "number": row.number,
        "patient": _user(row.patient),
        "organization": getattr(row.organization, "legal_name", None),
        "amount": row.amount,
        "paid_amount": row.paid_amount,
        "balance": row.balance,
        "currency": row.currency,
        "status": row.status,
        "gateway": row.gateway,
        "gateway_reference": row.gateway_ref,
        "due_at": _iso(row.due_at),
        "created_at": _iso(row.created_at),
    }


def _patient_scope(user, requested_patient=None):
    role = active_role(user)
    if role == "patient":
        return user.id
    return requested_patient


def patient_data(request, slug):
    from appointments.models import Appointment
    from clinical.models import ClinicalEncounter, Referral
    from communication.models import Notification
    from governance.models import Consent
    from operations.models import Admission, ImagingOrder
    from payments.models import Invoice, PaymentTransaction, Receipt
    from prescriptions.models import Prescription
    from services.models import InsuranceClaim, InsurancePreauthorization, LabOrder, PatientCoverage
    from accounts.models import PatientRelationship
    from .models import MedicationAdherenceEntry, MedicationRenewalRequest, WaitingRoomEntry

    user = request.user
    patient_id = user.id
    if slug in {"appointment-detail", "reschedule-appointment", "cancel-refund"}:
        qs = Appointment.objects.filter(patient=user).select_related("patient", "doctor").order_by("-date", "-start_time")
        return {"kind": "appointments", "records": [_appointment(row) for row in qs[:100]]}
    if slug == "virtual-waiting-room":
        rows = WaitingRoomEntry.objects.filter(patient=user).select_related("appointment__doctor", "organization").order_by("-created_at")[:50]
        return {"kind": "waiting_room", "records": [{
            "id": row.id, "appointment": _appointment(row.appointment),
            "organization": getattr(row.organization, "legal_name", None),
            "status": row.status, "queue_number": row.queue_number,
            "queue_position": row.queue_position, "device_status": row.device_status,
            "checked_in_at": _iso(row.checked_in_at), "ready_at": _iso(row.ready_at),
            "called_at": _iso(row.called_at), "joined_at": _iso(row.joined_at),
            "last_seen_at": _iso(row.last_seen_at),
        } for row in rows]}
    if slug in {"consultation-detail", "consultation-history"}:
        rows = ClinicalEncounter.objects.filter(patient=user).select_related("appointment", "doctor").order_by("-created_at")[:100]
        return {"kind": "consultations", "records": [{
            "id": row.id, "appointment": row.appointment_id, "doctor": _user(row.doctor),
            "status": row.status, "chief_complaint": row.chief_complaint,
            "assessment": row.assessment, "treatment_plan": row.treatment_plan,
            "safety_net_advice": row.safety_net_advice, "follow_up_date": str(row.follow_up_date or ""),
            "signed_at": _iso(row.signed_at), "created_at": _iso(row.created_at),
        } for row in rows]}
    if slug in {"prescription-detail", "refill-request", "medication-adherence", "allergy-medication-card"}:
        rows = Prescription.objects.filter(patient=user).select_related("doctor", "appointment").prefetch_related("items").order_by("-created_at")[:100]
        renewals = MedicationRenewalRequest.objects.filter(patient=user).select_related("prescription", "prescriber", "decided_by")[:100]
        adherence = MedicationAdherenceEntry.objects.filter(patient=user).select_related("prescription", "prescription_item")[:200]
        return {"kind": "prescriptions", "records": [{
            "id": row.id, "number": row.number, "doctor": _user(row.doctor), "status": row.status,
            "signed_at": _iso(row.signed_at), "expires_at": _iso(row.expires_at), "notes": row.notes,
            "items": [{"id": item.id, "medicine": item.medicine_name, "generic_name": item.generic_name,
                       "dosage": item.dosage, "frequency": item.frequency, "route": item.route,
                       "duration": item.duration, "quantity": item.quantity,
                       "dispensed_quantity": item.dispensed_quantity, "refills_allowed": item.refills_allowed}
                      for item in row.items.all()],
        } for row in rows],
        "renewals": [{"id": row.id, "prescription": row.prescription.number, "prescriber": _user(row.prescriber),
                      "reason": row.reason, "status": row.status, "decision_note": row.decision_note,
                      "decided_by": _user(row.decided_by), "decided_at": _iso(row.decided_at),
                      "created_at": _iso(row.created_at)} for row in renewals],
        "adherence": [{"id": row.id, "prescription": row.prescription.number,
                       "medicine": getattr(row.prescription_item, "medicine_name", None),
                       "scheduled_for": _iso(row.scheduled_for), "taken_at": _iso(row.taken_at),
                       "status": row.status, "note": row.note} for row in adherence]}
    if slug in {"laboratory-order-detail", "laboratory-result-trends"}:
        rows = LabOrder.objects.filter(patient=user).select_related("test", "referring_doctor").prefetch_related("results").order_by("-created_at")[:100]
        return {"kind": "laboratory", "records": [{
            "id": row.id, "test": row.test.name, "status": row.status, "priority": row.priority,
            "specimen_id": row.specimen_id, "collected_at": _iso(row.collected_at),
            "released_at": _iso(row.released_at), "result_released": row.result_released,
            "results": [{"id": result.id, "name": result.name,
                         "value": str(result.value_numeric) if result.value_numeric is not None else result.value_text,
                         "unit": result.unit, "reference_low": str(result.reference_low or ""),
                         "reference_high": str(result.reference_high or ""),
                         "interpretation": result.interpretation, "status": result.status,
                         "created_at": _iso(result.created_at)}
                        for result in row.results.all()] if row.result_released else [],
        } for row in rows]}
    if slug in {"imaging-order-detail", "diagnostic-viewer"}:
        rows = ImagingOrder.objects.filter(patient=user).select_related("organization", "ordering_clinician").order_by("-created_at")[:100]
        output = []
        for row in rows:
            report = getattr(row, "report", None)
            output.append({
                "id": row.id, "order_number": row.order_number, "modality": row.modality,
                "study_name": row.study_name, "status": row.status, "scheduled_at": _iso(row.scheduled_at),
                "performed_at": _iso(row.performed_at), "image_reference": row.image_reference,
                "report": ({"id": report.id, "findings": report.findings, "impression": report.impression,
                            "recommendations": report.recommendations, "critical": report.critical,
                            "status": report.status, "released_at": _iso(report.released_at)}
                           if report and report.status in {report.Status.VERIFIED, report.Status.RELEASED, report.Status.AMENDED} else None),
            })
        return {"kind": "imaging", "records": output}
    if slug in {"admission-detail", "ward-care-team", "discharge-summary"}:
        rows = Admission.objects.filter(patient=user).select_related("organization", "ward", "attending_clinician").prefetch_related("bed_allocations__bed").order_by("-admitted_at")[:50]
        output = []
        for row in rows:
            summary = getattr(row, "discharge_summary", None)
            output.append({
                "id": row.id, "admission_number": row.admission_number, "status": row.status,
                "organization": row.organization.legal_name, "ward": row.ward.name,
                "bed": _current_bed(row), "attending_clinician": _user(row.attending_clinician),
                "admitted_at": _iso(row.admitted_at), "discharged_at": _iso(row.discharged_at),
                "discharge_summary": ({"final_diagnosis": summary.final_diagnosis,
                                      "treatment_summary": summary.treatment_summary,
                                      "discharge_medications": summary.discharge_medications,
                                      "follow_up_plan": summary.follow_up_plan,
                                      "patient_instructions": summary.patient_instructions,
                                      "finalized_at": _iso(summary.finalized_at)} if summary and summary.finalized_at else None),
            })
        return {"kind": "admissions", "records": output}
    if slug == "referral-detail":
        rows = Referral.objects.filter(patient=user).select_related("referring_provider", "target_provider", "target_organization").order_by("-created_at")[:100]
        return {"kind": "referrals", "records": [{
            "id": row.id, "status": row.status, "priority": row.priority,
            "referring_provider": _user(row.referring_provider), "target_provider": _user(row.target_provider),
            "target_specialty": row.target_specialty, "target_facility": row.target_facility,
            "reason": row.reason, "clinical_summary": row.clinical_summary,
            "created_at": _iso(row.created_at),
        } for row in rows]}
    if slug in {"insurance-policy-detail", "preauthorization-detail", "claim-detail"}:
        coverages = PatientCoverage.objects.filter(patient=user).select_related("policy", "provider")
        preauths = InsurancePreauthorization.objects.filter(patient=user).select_related("policy", "provider")
        claims = InsuranceClaim.objects.filter(patient=user).select_related("provider", "policy")
        return {"kind": "insurance", "coverages": [{"id": row.id, "member_id": row.member_id, "active": row.active, "is_current": row.is_current,
                                                        "provider": row.provider.display_name, "policy": row.policy.name,
                                                        "effective_from": str(row.effective_from), "expires_on": str(row.expires_on or "")}
                                                       for row in coverages[:50]],
                "preauthorizations": [{"id": row.id, "number": row.authorization_number, "service": row.service_name,
                                        "requested_amount": row.requested_amount, "approved_amount": row.approved_amount,
                                        "status": row.status, "decision_reason": row.decision_reason,
                                        "created_at": _iso(row.created_at)} for row in preauths[:50]],
                "claims": [{"id": row.id, "number": getattr(row, "claim_number", row.id), "status": row.status,
                            "amount": getattr(row, "amount", getattr(row, "claimed_amount", 0)),
                            "created_at": _iso(row.created_at)} for row in claims[:50]]}
    if slug in {"payment-methods", "mobile-money-status", "receipt-detail"}:
        invoices = Invoice.objects.filter(patient=user).select_related("organization").prefetch_related("payments")[:100]
        payments = PaymentTransaction.objects.filter(invoice__patient=user).select_related("invoice")[:100]
        receipts = Receipt.objects.filter(payment__invoice__patient=user).select_related("payment__invoice")[:100]
        return {"kind": "billing", "invoices": [_invoice(row) for row in invoices],
                "payments": [{"id": row.id, "number": row.number, "invoice": row.invoice.number,
                              "amount": row.amount, "method": row.method, "status": row.status,
                              "reference": row.reference, "created_at": _iso(row.created_at),
                              "confirmed_at": _iso(row.confirmed_at)} for row in payments],
                "receipts": [{"id": row.id, "number": row.number, "payment": row.payment.number,
                              "invoice": row.payment.invoice.number, "amount": row.payment.amount,
                              "created_at": _iso(row.created_at)} for row in receipts]}
    if slug in {"consent-centre", "family-access", "caregiver-invitation"}:
        consents = Consent.objects.filter(patient=user).select_related("granted_to")[:100]
        relationships = PatientRelationship.objects.filter(Q(patient=user) | Q(caregiver=user)).select_related("patient", "caregiver")[:100]
        return {"kind": "consent_authority",
                "consents": [{"id": row.id, "type": row.consent_type, "purpose": row.purpose,
                              "status": row.status, "granted_to": _user(row.granted_to),
                              "valid_until": _iso(row.valid_until), "granted_at": _iso(row.granted_at)} for row in consents],
                "relationships": [{"id": row.id, "patient": _user(row.patient), "caregiver": _user(row.caregiver),
                                   "relationship": row.relationship, "status": row.status,
                                   "can_book": row.can_book, "can_view_records": row.can_view_records,
                                   "can_manage_billing": row.can_manage_billing,
                                   "can_receive_notifications": row.can_receive_notifications,
                                   "expires_at": _iso(row.expires_at)} for row in relationships]}
    if slug == "notification-inbox":
        rows = Notification.objects.filter(user=user).prefetch_related("deliveries")[:200]
        return {"kind": "notifications", "unread": Notification.objects.filter(user=user, is_read=False).count(),
                "records": [{"id": row.id, "title": row.title, "body": row.body, "kind": row.kind,
                             "priority": row.priority, "action_url": row.action_url, "is_read": row.is_read,
                             "created_at": _iso(row.created_at),
                             "deliveries": [{"channel": d.channel, "status": d.status, "attempts": d.attempts,
                                             "last_error": d.last_error} for d in row.deliveries.all()]}
                            for row in rows]}
    return None


def clinical_data(request, slug):
    from appointments.models import Appointment
    from clinical.models import ClinicalEncounter
    from registry.models import CareRelationship
    from operations.models import Admission, StaffShift
    from services.models import LabResult
    from operations.models import ImagingReport
    from .models import CareConference, ClinicalTask, GeneratedClinicalDocument, MedicationRenewalRequest

    user = request.user
    if slug in {"my-patients", "patient-detail"}:
        relationships = CareRelationship.objects.filter(practitioner=user, status=CareRelationship.Status.ACTIVE).select_related("patient")
        return {"kind": "care_relationships", "records": [{"id": row.id, "patient": _user(row.patient),
                                                               "relationship_type": row.relationship_type,
                                                               "starts_at": _iso(row.starts_at), "ends_at": _iso(row.ends_at)}
                                                              for row in relationships[:250]]}
    if slug in {"daily-inpatients"}:
        org = active_organization(user)
        qs = Admission.objects.select_related("patient", "ward").prefetch_related("bed_allocations__bed").exclude(status__in=["discharged", "cancelled"])
        if org:
            qs = qs.filter(organization=org)
        qs = qs.filter(Q(attending_clinician=user) | Q(patient__care_relationships__practitioner=user)).distinct()
        return {"kind": "inpatients", "records": [{"id": row.id, "admission_number": row.admission_number,
                                                       "patient": _user(row.patient), "ward": row.ward.name,
                                                       "bed": _current_bed(row), "status": row.status,
                                                       "admitted_at": _iso(row.admitted_at)} for row in qs[:200]]}
    if slug in {"consultation-history"}:
        rows = ClinicalEncounter.objects.filter(doctor=user).select_related("patient", "appointment")[:200]
        return {"kind": "consultations", "records": [{"id": row.id, "patient": _user(row.patient),
                                                         "status": row.status, "assessment": row.assessment,
                                                         "treatment_plan": row.treatment_plan,
                                                         "signed_at": _iso(row.signed_at), "created_at": _iso(row.created_at)} for row in rows]}
    if slug in {"results-inbox", "critical-results"}:
        lab = LabResult.objects.filter(order__referring_doctor=user).select_related("order__patient", "order__test")
        imaging = ImagingReport.objects.filter(order__ordering_clinician=user).select_related("order__patient", "order")
        if slug == "critical-results":
            lab = lab.filter(interpretation=LabResult.Interpretation.CRITICAL)
            imaging = imaging.filter(critical=True)
        return {"kind": "clinical_results",
                "laboratory": [{"id": row.id, "patient": _user(row.order.patient), "test": row.name,
                                "value": str(row.value_numeric) if row.value_numeric is not None else row.value_text,
                                "unit": row.unit, "interpretation": row.interpretation,
                                "status": row.status, "created_at": _iso(row.created_at)} for row in lab[:150]],
                "imaging": [{"id": row.id, "patient": _user(row.order.patient),
                             "study": row.order.study_name, "impression": row.impression,
                             "critical": row.critical, "status": row.status,
                             "created_at": _iso(row.created_at)} for row in imaging[:150]]}
    if slug in {"clinical-task-inbox", "order-entry", "admission-orders", "procedure-documentation"}:
        rows = ClinicalTask.objects.filter(Q(assigned_to=user) | Q(created_by=user)).select_related("patient", "assigned_to")[:200]
        return {"kind": "clinical_tasks", "records": [{"id": row.id, "patient": _user(row.patient),
                                                          "task_type": row.task_type, "instructions": row.instructions,
                                                          "assigned_to": _user(row.assigned_to), "status": row.status,
                                                          "due_at": _iso(row.due_at), "completed_at": _iso(row.completed_at)} for row in rows]}
    if slug == "medication-renewals":
        rows = MedicationRenewalRequest.objects.filter(prescriber=user).select_related("patient", "prescription")[:200]
        return {"kind": "medication_renewals", "records": [{"id": row.id, "patient": _user(row.patient),
                                                               "prescription": row.prescription.number, "reason": row.reason,
                                                               "status": row.status, "decision_note": row.decision_note,
                                                               "created_at": _iso(row.created_at)} for row in rows]}
    if slug == "on-call-schedule":
        rows = StaffShift.objects.filter(staff=user, shift_type="on_call").select_related("department")[:100]
        return {"kind": "on_call", "records": [{"id": row.id, "starts_at": _iso(row.starts_at),
                                                   "ends_at": _iso(row.ends_at), "status": row.status,
                                                   "department": getattr(row.department, "name", None),
                                                   "location": row.location, "notes": row.notes} for row in rows]}
    if slug == "multidisciplinary-team":
        rows = CareConference.objects.filter(Q(chair=user) | Q(participants=user)).select_related("patient", "chair").prefetch_related("participants").distinct()[:100]
        return {"kind": "care_conferences", "records": [{"id": row.id, "patient": _user(row.patient),
                                                            "title": row.title, "scheduled_at": _iso(row.scheduled_at),
                                                            "chair": _user(row.chair), "participants": [_user(p) for p in row.participants.all()],
                                                            "agenda": row.agenda, "minutes": row.minutes, "status": row.status} for row in rows]}
    if slug in {"medical-certificates", "sick-notes", "referral-letters", "discharge-summary-builder", "medical-documents"}:
        rows = GeneratedClinicalDocument.objects.filter(Q(created_by=user) | Q(signed_by=user)).select_related("patient")[:100]
        return {"kind": "clinical_documents", "records": [{"id": row.id, "public_id": row.public_id,
                                                               "patient": _user(row.patient), "type": row.document_type,
                                                               "title": row.title, "status": row.status,
                                                               "verification_code": row.verification_code,
                                                               "signed_at": _iso(row.signed_at)} for row in rows]}
    return None


def nursing_data(request, slug):
    from operations.models import Admission
    from workforce.models import MedicationAdministration, PatientVisit
    from .models import ClinicalTask

    user = request.user
    org = active_organization(user)
    if slug in {"assigned-patients", "ward-patient-list", "patient-nursing-chart"}:
        qs = Admission.objects.select_related("patient", "ward", "attending_clinician").prefetch_related("bed_allocations__bed").exclude(status__in=["discharged", "cancelled"])
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "nursing_patients", "records": [{"id": row.id, "patient": _user(row.patient),
                                                            "admission_number": row.admission_number, "ward": row.ward.name,
                                                            "bed": _current_bed(row), "status": row.status,
                                                            "attending_clinician": _user(row.attending_clinician)} for row in qs[:200]]}
    if slug in {"emar", "due-medications", "overdue-medications", "medication-omissions"}:
        rows = MedicationAdministration.objects.filter(nurse=user).select_related("visit__patient").order_by("-scheduled_for", "-created_at")[:250]
        now = timezone.now()
        if slug == "due-medications":
            rows = [row for row in rows if row.scheduled_for and now - timedelta(minutes=30) <= row.scheduled_for <= now + timedelta(hours=2)]
        elif slug == "overdue-medications":
            rows = [row for row in rows if row.scheduled_for and row.scheduled_for < now and row.status not in {row.Status.GIVEN}]
        elif slug == "medication-omissions":
            rows = [row for row in rows if row.status == row.Status.MISSED]
        return {"kind": "medication_administration", "records": [{"id": row.id, "patient": _user(row.visit.patient),
                                                                     "medication": row.medication, "dose": row.dose,
                                                                     "route": row.route, "scheduled_for": _iso(row.scheduled_for),
                                                                     "administered_at": _iso(getattr(row, "administered_at", None)),
                                                                     "status": row.status, "notes": row.notes} for row in rows]}
    if slug in {"supply-requests", "equipment-checklist", "discharge-checklist"}:
        rows = ClinicalTask.objects.filter(assigned_to=user, workflow_case__page_slug=slug).select_related("patient")[:100]
        return {"kind": "nursing_tasks", "records": [{"id": row.id, "patient": _user(row.patient),
                                                          "task_type": row.task_type, "instructions": row.instructions,
                                                          "status": row.status, "due_at": _iso(row.due_at)} for row in rows]}
    return None


def reception_data(request, slug):
    from appointments.models import Appointment, Availability
    from enterprise.models import DuplicatePatientCandidate
    from .models import CallCentreCallback, QueueTicket

    org = active_organization(request.user)
    if slug in {"appointment-calendar", "provider-schedules", "create-appointment", "cancel-appointment", "reschedule-appointment"}:
        qs = Appointment.objects.select_related("patient", "doctor")
        if org:
            qs = qs.filter(doctor__staff_memberships__organization=org).distinct()
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        slots = Availability.objects.select_related("doctor")
        if org:
            slots = slots.filter(doctor__staff_memberships__organization=org).distinct()
        return {"kind": "front_desk_calendar", "appointments": [_appointment(row) for row in qs.order_by("date", "start_time")[:500]],
                "availability": [{"id": row.id, "provider": _user(row.doctor), "weekday": row.weekday,
                                  "start_time": str(row.start_time), "end_time": str(row.end_time),
                                  "slot_minutes": row.slot_minutes, "is_active": row.is_active} for row in slots[:500]]}
    if slug in {"patient-arrival-board", "queue-ticket", "walk-in-conversion"}:
        qs = QueueTicket.objects.select_related("patient", "appointment", "department")
        if org:
            qs = qs.filter(organization=org)
        records = [{"id": row.id, "number": row.number, "patient": _user(row.patient),
                    "appointment": row.appointment_id, "department": getattr(row.department, "name", None),
                    "status": row.status, "counter": row.counter,
                    "issued_at": _iso(row.issued_at), "called_at": _iso(row.called_at)} for row in qs[:300]]
        if slug == "patient-arrival-board":
            # The live arrival queue is the PatientVisit engine; QueueTicket is
            # a separate counter system. Show today's visits so reception sees
            # and advances real arrivals.
            from workforce.models import PatientVisit

            visits = PatientVisit.objects.select_related("patient").filter(checked_in_at__date=timezone.localdate())
            if org:
                visits = visits.filter(organization=org)
            records += [
                {
                    "id": row.id,
                    "visit_number": row.visit_number,
                    "queue_number": row.queue_number,
                    "patient_name": row.patient.display_name,
                    "reason": row.reason,
                    "status": row.status,
                    "priority": row.priority,
                    "checked_in_at": _iso(row.checked_in_at),
                    "_dataset": "visits",
                }
                for row in visits.order_by("queue_number")[:300]
            ]
        return {"kind": "queue", "records": records}
    if slug in {"duplicate-warning"}:
        qs = DuplicatePatientCandidate.objects.select_related("patient_a__patient", "patient_b__patient").filter(status="pending")
        if org and hasattr(DuplicatePatientCandidate, "organization"):
            qs = qs.filter(organization=org)
        return {"kind": "duplicates", "records": [{"id": row.id, "patient_a": _mpi(row.patient_a),
                                                      "patient_b": _mpi(row.patient_b), "score": row.score,
                                                      "matching_fields": row.matching_fields, "status": row.status} for row in qs[:200]]}
    if slug == "call-centre":
        qs = CallCentreCallback.objects.select_related("patient", "assigned_to")
        if org:
            qs = qs.filter(workflow_case__organization=org)
        return {"kind": "callbacks", "records": [{"id": row.id, "patient": _user(row.patient), "phone": row.phone,
                                                     "reason": row.reason, "scheduled_for": _iso(row.scheduled_for),
                                                     "assigned_to": _user(row.assigned_to), "status": row.status,
                                                     "outcome": row.outcome, "attempts": row.attempts} for row in qs[:200]]}
    return None


def records_data(request, slug):
    from enterprise.models import DuplicatePatientCandidate, RecordsRequest

    org = active_organization(request.user)
    if slug in {"master-patient-index", "duplicate-inbox", "patient-comparison", "merge-wizard", "unmerge-review", "identity-conflicts"}:
        qs = DuplicatePatientCandidate.objects.select_related("patient_a__patient", "patient_b__patient")
        return {"kind": "mpi", "records": [{"id": row.id, "patient_a": _mpi(row.patient_a), "patient_b": _mpi(row.patient_b),
                                               "score": row.score, "matching_fields": row.matching_fields, "status": row.status,
                                               "created_at": _iso(row.created_at)} for row in qs[:300]]}
    qs = RecordsRequest.objects.select_related("patient", "requested_by", "assigned_to")
    if org:
        qs = qs.filter(Q(organization=org) | Q(organization__isnull=True))
    return {"kind": "records_requests", "records": [{"id": row.id, "number": row.request_number,
                                                        "type": row.request_type, "patient": _user(row.patient),
                                                        "reason": row.reason, "status": row.status,
                                                        "assigned_to": _user(row.assigned_to), "due_at": _iso(row.due_at),
                                                        "created_at": _iso(row.created_at)} for row in qs[:300]]}


def finance_data(request, slug):
    from payments.models import (ApprovalLimit, CashierShift, DepartmentBudget, Expense, FinancialPeriod, Invoice, JournalEntry, LedgerAccount, PaymentTransaction, Posting, RefundRequest, ReconciliationRun, SupplierInvoice)

    org = active_organization(request.user)
    invoices = Invoice.objects.select_related("patient", "organization")
    if org:
        invoices = invoices.filter(organization=org)
    if slug in {"patient-account", "pending-payments", "accounts-receivable", "ageing-analysis"}:
        qs = invoices
        if slug in {"pending-payments", "accounts-receivable", "ageing-analysis"}:
            qs = qs.exclude(status__in=[Invoice.Status.PAID, Invoice.Status.REFUNDED, Invoice.Status.VOID])
        return {"kind": "receivables", "records": [_invoice(row) for row in qs[:300]],
                "totals": {"invoiced": qs.aggregate(total=Sum("amount"))["total"] or 0,
                           "outstanding": sum(row.balance for row in qs[:1000])}}
    if slug in {"cash-drawer", "shift-transactions", "end-of-day", "daily-cashbook"}:
        shifts = CashierShift.objects.select_related("cashier", "organization")
        if org:
            shifts = shifts.filter(organization=org)
        payments = PaymentTransaction.objects.select_related("invoice", "received_by")
        if org:
            payments = payments.filter(invoice__organization=org)
        return {"kind": "cashbook", "shifts": [{"id": row.id, "cashier": _user(row.cashier),
                                                   "opening_float": row.opening_float, "expected_cash": row.expected_cash,
                                                   "closing_cash": row.closing_cash, "variance": row.variance,
                                                   "status": row.status, "opened_at": _iso(row.opened_at),
                                                   "closed_at": _iso(row.closed_at)} for row in shifts[:100]],
                "payments": [{"id": row.id, "number": row.number, "invoice": row.invoice.number,
                              "amount": row.amount, "method": row.method, "status": row.status,
                              "reference": row.reference, "received_by": _user(row.received_by),
                              "created_at": _iso(row.created_at)} for row in payments[:300]]}
    if slug in {"refund-request", "refund-detail"}:
        qs = RefundRequest.objects.select_related("payment__invoice", "requested_by", "approved_by")
        if org:
            qs = qs.filter(payment__invoice__organization=org)
        return {"kind": "refunds", "records": [{"id": row.id, "number": row.number,
                                                   "invoice": row.payment.invoice.number, "amount": row.amount,
                                                   "status": row.status, "reason": row.reason,
                                                   "requested_by": _user(row.requested_by), "approved_by": _user(row.approved_by),
                                                   "created_at": _iso(row.created_at)} for row in qs[:200]]}
    if slug in {"bank-reconciliation", "mobile-money-reconciliation", "gateway-reconciliation", "payment-reconciliation"}:
        qs = ReconciliationRun.objects.select_related("organization", "created_by", "completed_by")
        if org:
            qs = qs.filter(organization=org)
        kind_map = {"bank-reconciliation": "bank", "mobile-money-reconciliation": "mobile_money", "gateway-reconciliation": "gateway"}
        if slug in kind_map:
            qs = qs.filter(kind=kind_map[slug])
        return {"kind": "reconciliations", "records": [{"id": row.id, "number": row.number, "kind": row.kind,
                    "period_start": _iso(row.period_start), "period_end": _iso(row.period_end),
                    "expected_amount": row.expected_amount, "actual_amount": row.actual_amount,
                    "variance": row.variance, "status": row.status, "notes": row.notes,
                    "created_by": _user(row.created_by), "completed_by": _user(row.completed_by)} for row in qs[:250]]}
    if slug in {"expense-register", "expenses"}:
        qs = Expense.objects.select_related("organization", "department", "requested_by", "approved_by")
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "expenses", "records": [{"id": row.id, "number": row.number, "vendor": row.vendor,
                    "category": row.category, "description": row.description, "amount": row.amount,
                    "currency": row.currency, "status": row.status, "incurred_on": str(row.incurred_on),
                    "reference": row.reference, "department": getattr(row.department, "name", None),
                    "requested_by": _user(row.requested_by), "approved_by": _user(row.approved_by)} for row in qs[:300]]}
    if slug in {"supplier-invoices", "supplier-payments", "accounts-payable"}:
        qs = SupplierInvoice.objects.select_related("organization", "created_by", "approved_by")
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "supplier_invoices", "records": [{"id": row.id, "supplier": row.supplier_name,
                    "invoice_number": row.invoice_number, "amount": row.amount, "paid_amount": row.paid_amount,
                    "balance": row.balance, "currency": row.currency, "status": row.status,
                    "invoice_date": str(row.invoice_date), "due_date": str(row.due_date or ""),
                    "reference": row.reference} for row in qs[:300]]}
    if slug in {"budget-management", "department-budgets"}:
        qs = DepartmentBudget.objects.select_related("organization", "department", "period", "approved_by")
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "budgets", "records": [{"id": row.id, "department": getattr(row.department, "name", None),
                    "period": row.period.name, "category": row.category, "amount": row.amount,
                    "committed_amount": row.committed_amount, "spent_amount": row.spent_amount,
                    "available_amount": row.available_amount, "approved_by": _user(row.approved_by)} for row in qs[:250]]}
    if slug == "approval-limits":
        qs = ApprovalLimit.objects.select_related("organization")
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "approval_limits", "records": [{"id": row.id, "role_code": row.role_code,
                    "operation_type": row.operation_type, "maximum_amount": row.maximum_amount,
                    "currency": row.currency, "requires_second_approval": row.requires_second_approval,
                    "active": row.active} for row in qs[:250]]}
    if slug in {"period-close", "period-closing", "financial-periods"}:
        qs = FinancialPeriod.objects.select_related("organization", "created_by", "closed_by")
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "financial_periods", "records": [{"id": row.id, "name": row.name,
                    "starts_on": str(row.starts_on), "ends_on": str(row.ends_on), "status": row.status,
                    "created_by": _user(row.created_by), "closed_by": _user(row.closed_by),
                    "closed_at": _iso(row.closed_at)} for row in qs[:100]]}
    if slug in {"journal-entries", "general-ledger", "trial-balance", "income-statement", "balance-sheet", "cash-flow", "tax-report"}:
        entries = JournalEntry.objects.prefetch_related("postings__account")[:300]
        accounts = LedgerAccount.objects.filter(active=True).prefetch_related("postings")
        account_rows = []
        for account in accounts:
            debits = sum(p.amount for p in account.postings.all() if p.direction == "debit")
            credits = sum(p.amount for p in account.postings.all() if p.direction == "credit")
            account_rows.append({"id": account.id, "code": account.code, "name": account.name,
                                 "type": account.account_type, "debits": debits, "credits": credits,
                                 "balance": debits - credits})
        return {"kind": "ledger", "entries": [{"id": row.id, "reference": row.reference,
                                                  "description": row.description, "currency": row.currency,
                                                  "total_debits": row.total_debits, "total_credits": row.total_credits,
                                                  "balanced": row.is_balanced, "posted_at": _iso(row.posted_at)} for row in entries],
                "accounts": account_rows}
    return None



def _org_owner_account(user):
    org = active_organization(user)
    return getattr(org, "owner", None) if org else None


def pharmacy_data(request, slug):
    """Canonical pharmacy, dispensing and stock data for pharmacist/store roles."""
    from operations.models import InventoryBatch, InventoryItem, PurchaseOrder, StockMovement
    from services.models import DispensingRecord, PharmacyOrder

    user = request.user
    org = active_organization(user)
    pharmacy_account = _org_owner_account(user)

    if slug in {"prescription-workspace", "dispensing-labels", "label-printing", "prescription-clarification", "substitution-authorization", "pharmacist-intervention", "patient-medication-history"}:
        orders = PharmacyOrder.objects.select_related("patient", "pharmacy").order_by("-created_at")
        if active_role(user) == "pharmacy":
            orders = orders.filter(pharmacy=user)
        elif pharmacy_account:
            orders = orders.filter(Q(pharmacy=pharmacy_account) | Q(dispensing_records__pharmacist=user)).distinct()
        else:
            orders = orders.filter(dispensing_records__pharmacist=user).distinct()
        records = []
        for order in orders[:250]:
            dispensing = order.dispensing_records.select_related("pharmacist").prefetch_related("items").order_by("-created_at").first()
            records.append({
                "id": order.id,
                "reference": f"RX-{order.prescription_id}",
                "patient": _user(order.patient),
                "status": order.status,
                "pharmacy": getattr(order.pharmacy, "display_name", None),
                "created_at": _iso(order.created_at),
                "dispensing": ({
                    "id": dispensing.id,
                    "status": dispensing.status,
                    "pharmacist": _user(dispensing.pharmacist),
                    "clarification_note": dispensing.clarification_note,
                    "substitution_authorised_by": dispensing.substitution_authorised_by,
                    "counselling_notes": dispensing.counselling_notes,
                    "dispensed_at": _iso(dispensing.dispensed_at),
                    "items": [{
                        "medicine": item.medicine_name,
                        "prescribed_quantity": item.prescribed_quantity,
                        "dispensed_quantity": item.dispensed_quantity,
                        "batch_number": item.batch_number,
                        "expiry_date": str(item.expiry_date or ""),
                        "substituted_product": item.substituted_product,
                        "label_instructions": item.label_instructions,
                    } for item in dispensing.items.all()],
                } if dispensing else None),
            })
        return {"kind": "pharmacy_orders", "records": records}

    if slug in {"controlled-drug-register", "narcotics-balance", "stock-transfer", "stock-adjustment", "stock-count", "variance-investigation", "reorder-recommendations", "stock-valuation", "expiry-calendar", "cold-chain-chart", "temperature-excursion", "damaged-stock", "quarantine-stock", "product-recall", "drug-return"}:
        items = InventoryItem.objects.select_related("organization").prefetch_related("batches")
        if org:
            items = items.filter(organization=org)
        if slug in {"controlled-drug-register", "narcotics-balance"}:
            items = items.filter(controlled=True)
        if slug in {"cold-chain-chart", "temperature-excursion"}:
            items = items.filter(requires_cold_chain=True)
        today = timezone.localdate()
        records = []
        for item in items[:300]:
            batches = list(item.batches.all())
            quantity = sum(batch.quantity_available for batch in batches)
            records.append({
                "id": item.id,
                "reference": item.sku,
                "name": item.name,
                "category": item.category,
                "unit": item.unit,
                "controlled": item.controlled,
                "requires_cold_chain": item.requires_cold_chain,
                "reorder_level": item.reorder_level,
                "quantity_available": quantity,
                "status": "low_stock" if quantity <= item.reorder_level else "available",
                "batches": [{
                    "id": batch.id,
                    "batch_number": batch.batch_number,
                    "expiry_date": str(batch.expiry_date),
                    "quantity_available": batch.quantity_available,
                    "unit_cost": batch.unit_cost,
                    "selling_price": batch.selling_price,
                    "storage_location": batch.storage_location,
                    "supplier": batch.supplier_name,
                    "recalled": batch.recalled,
                    "days_to_expiry": (batch.expiry_date - today).days if batch.expiry_date else None,
                } for batch in batches],
            })
        return {"kind": "inventory", "records": records}

    if slug in {"goods-received", "purchase-order-detail", "supplier-invoice-matching", "supplier-management"}:
        orders = PurchaseOrder.objects.select_related("organization", "created_by", "approved_by").prefetch_related("items")
        if org:
            orders = orders.filter(organization=org)
        return {"kind": "purchase_orders", "records": [{
            "id": row.id,
            "reference": row.number,
            "supplier": row.supplier_name,
            "supplier_contact": row.supplier_contact,
            "status": row.status,
            "expected_on": str(row.expected_on or ""),
            "approved_by": _user(row.approved_by),
            "created_at": _iso(row.created_at),
            "items": [{
                "description": item.description or item.inventory_item.name,
                "quantity": item.quantity,
                "quantity_received": item.quantity_received,
                "unit_cost": item.unit_cost,
            } for item in row.items.all()],
        } for row in orders[:250]]}

    if slug in {"stock-movements", "pharmacy-sales-reports"}:
        movements = StockMovement.objects.select_related("batch__item", "created_by")
        if org:
            movements = movements.filter(batch__item__organization=org)
        return {"kind": "stock_movements", "records": [{
            "id": row.id,
            "reference": row.reference,
            "item": row.batch.item.name,
            "batch_number": row.batch.batch_number,
            "movement_type": row.movement_type,
            "quantity": row.quantity,
            "balance_after": row.balance_after,
            "reason": row.reason,
            "created_by": _user(row.created_by),
            "created_at": _iso(row.created_at),
            "status": "completed",
        } for row in movements[:400]]}
    return None


def laboratory_data(request, slug):
    """Canonical laboratory worklists, specimens, results and quality records."""
    from services.models import LabOrder, LabResult, LabTestPanel, SpecimenEvent
    from enterprise.models import EnterpriseRecord

    user = request.user
    org = active_organization(user)
    lab_account = _org_owner_account(user)
    orders = LabOrder.objects.select_related("patient", "lab", "test", "referring_doctor", "collected_by").prefetch_related("results", "specimen_events").order_by("-created_at")
    if active_role(user) == "lab":
        orders = orders.filter(lab=user)
    elif lab_account:
        orders = orders.filter(Q(lab=lab_account) | Q(collected_by=user) | Q(results__entered_by=user) | Q(results__verified_by=user)).distinct()
    else:
        orders = orders.filter(Q(collected_by=user) | Q(results__entered_by=user) | Q(results__verified_by=user)).distinct()

    worklist_slugs = {"specimen-collection", "phlebotomy-queue", "accessioning", "barcode-labels", "barcode-scanner", "rejected-specimens", "transport-manifest", "aliquot-creation", "storage-location", "result-entry", "result-comparison", "validation-queue", "release-queue", "critical-results", "laboratory-report-printing"}
    if slug in worklist_slugs:
        if slug == "rejected-specimens":
            orders = orders.filter(status="rejected")
        elif slug == "validation-queue":
            orders = orders.filter(results__status__in=["preliminary", "entered"]).distinct()
        elif slug == "release-queue":
            orders = orders.filter(result_released=False, results__status__in=["verified", "validated"]).distinct()
        elif slug == "critical-results":
            orders = orders.filter(results__interpretation="critical").distinct()
        return {"kind": "laboratory_worklist", "records": [{
            "id": row.id,
            "reference": row.specimen_id or f"LAB-{row.id}",
            "patient": _user(row.patient),
            "test": row.test.name,
            "sample_type": row.test.sample_type,
            "priority": row.priority,
            "status": row.status,
            "referring_doctor": _user(row.referring_doctor),
            "collected_by": _user(row.collected_by),
            "collected_at": _iso(row.collected_at),
            "received_at": _iso(row.received_at),
            "released_at": _iso(row.released_at),
            "rejection_reason": row.rejection_reason,
            "events": [{
                "event_type": event.event_type,
                "barcode": event.barcode,
                "location": event.location,
                "notes": event.notes,
                "occurred_at": _iso(event.occurred_at),
                "performed_by": _user(event.performed_by),
            } for event in row.specimen_events.all()],
            "results": [{
                "id": result.id,
                "name": result.name,
                "value": str(result.value_numeric) if result.value_numeric is not None else result.value_text,
                "unit": result.unit,
                "reference_low": str(result.reference_low or ""),
                "reference_high": str(result.reference_high or ""),
                "interpretation": result.interpretation,
                "status": result.status,
                "entered_by": _user(result.entered_by),
                "verified_by": _user(result.verified_by),
            } for result in row.results.all()],
        } for row in orders[:300]]}

    if slug in {"test-panels", "laboratory-catalogue"}:
        panels = LabTestPanel.objects.select_related("lab").prefetch_related("items__test")
        if active_role(user) == "lab":
            panels = panels.filter(lab=user)
        elif lab_account:
            panels = panels.filter(lab=lab_account)
        return {"kind": "test_panels", "records": [{
            "id": panel.id,
            "reference": panel.code,
            "name": panel.name,
            "description": panel.description,
            "price": panel.price,
            "status": "active" if panel.active else "inactive",
            "tests": [{"id": item.test_id, "name": item.test.name, "sequence": item.sequence, "required": item.required} for item in panel.items.all()],
        } for panel in panels[:200]]}

    if slug in {"microbiology", "antibiotic-sensitivity", "histopathology", "blood-bank-inventory", "crossmatch", "transfusion-compatibility", "reagent-inventory", "equipment-register", "calibration-calendar", "quality-control", "levey-jennings", "turnaround-time"}:
        type_map = {
            "microbiology": ["microbiology_culture"], "antibiotic-sensitivity": ["antibiotic_sensitivity"],
            "histopathology": ["histopathology_case"], "blood-bank-inventory": ["blood_bank"],
            "crossmatch": ["crossmatch"], "transfusion-compatibility": ["transfusion_compatibility"],
            "reagent-inventory": ["reagent_lot"], "equipment-register": ["laboratory_equipment"],
            "calibration-calendar": ["equipment_calibration"], "quality-control": ["laboratory_qc"],
            "levey-jennings": ["laboratory_qc"], "turnaround-time": ["laboratory_tat"],
        }
        qs = EnterpriseRecord.objects.filter(record_type__in=type_map.get(slug, []))
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "laboratory_quality", "records": [{
            "id": row.id, "public_id": row.public_id, "reference": row.reference,
            "title": row.title, "summary": row.summary, "status": row.status,
            "priority": row.priority, "payload": row.payload,
            "occurred_at": _iso(row.occurred_at), "updated_at": _iso(row.updated_at),
        } for row in qs[:300]]}
    return None


def emergency_data(request, slug):
    from operations.models import AmbulanceDispatch, EmergencyCase
    from enterprise.models import AmbulanceTelemetry, AmbulanceVehicle, EnterpriseRecord

    user = request.user
    org = active_organization(user)
    if slug in {"emergency-command", "emergency-call-intake", "incident-detail", "emergency-triage", "trauma-chart", "resuscitation-timeline", "medication-timeline", "procedure-timeline", "gcs-chart", "emergency-observation", "transfer-form", "receiving-handover", "mass-casualty"}:
        cases = EmergencyCase.objects.select_related("organization", "patient", "assigned_clinician").order_by("-arrival_at")
        if org:
            cases = cases.filter(organization=org)
        return {"kind": "emergency_cases", "records": [{
            "id": row.id, "reference": row.case_number, "patient": _user(row.patient),
            "arrival_mode": row.arrival_mode, "acuity": row.acuity,
            "chief_complaint": row.chief_complaint, "triage_notes": row.triage_notes,
            "status": row.status, "assigned_clinician": _user(row.assigned_clinician),
            "disposition": row.disposition, "arrival_at": _iso(row.arrival_at),
            "treatment_started_at": _iso(row.treatment_started_at), "closed_at": _iso(row.closed_at),
        } for row in cases[:300]]}
    if slug in {"live-dispatch-map", "ambulance-detail", "crew-roster", "live-telemetry", "route-eta", "ambulance-equipment", "ambulance-cleaning", "paramedic-workspace"}:
        dispatches = AmbulanceDispatch.objects.select_related("organization", "patient", "dispatcher", "paramedic").order_by("-requested_at")
        vehicles = AmbulanceVehicle.objects.select_related("organization")
        if org:
            dispatches = dispatches.filter(organization=org)
            vehicles = vehicles.filter(organization=org)
        telemetry_by_dispatch = {}
        telemetry = AmbulanceTelemetry.objects.select_related("vehicle", "dispatch").filter(dispatch__in=dispatches).order_by("dispatch_id", "-recorded_at")
        for row in telemetry:
            telemetry_by_dispatch.setdefault(row.dispatch_id, row)
        records = []
        for row in dispatches[:300]:
            point = telemetry_by_dispatch.get(row.id)
            records.append({
                "id": row.id, "reference": row.dispatch_number, "patient": _user(row.patient),
                "caller_name": row.caller_name, "caller_phone": row.caller_phone,
                "pickup_location": row.pickup_location, "destination": row.destination,
                "priority": row.priority, "status": row.status,
                "dispatcher": _user(row.dispatcher), "paramedic": _user(row.paramedic),
                "ambulance_identifier": row.ambulance_identifier,
                "requested_at": _iso(row.requested_at), "dispatched_at": _iso(row.dispatched_at),
                "arrived_scene_at": _iso(row.arrived_scene_at), "completed_at": _iso(row.completed_at),
                "payload": ({
                    "latitude": point.latitude, "longitude": point.longitude,
                    "speed_kph": point.speed_kph, "heading": point.heading,
                    "accuracy_m": point.accuracy_m, "recorded_at": _iso(point.recorded_at),
                } if point else {}),
            })
        return {"kind": "ambulance_dispatch", "records": records, "vehicles": [{
            "id": vehicle.id, "call_sign": vehicle.call_sign,
            "registration_number": vehicle.registration_number,
            "vehicle_type": vehicle.vehicle_type, "status": vehicle.status,
            "crew": vehicle.crew, "equipment": vehicle.equipment,
            "active": vehicle.active,
        } for vehicle in vehicles[:150]]}
    record_types = {
        "offline-paramedic": ["pre_hospital_record"],
        "ambulance-equipment": ["ambulance_equipment_check"],
        "ambulance-cleaning": ["ambulance_cleaning_check"],
    }
    if slug in record_types:
        qs = EnterpriseRecord.objects.filter(record_type__in=record_types[slug])
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "emergency_operations", "records": [{
            "id": row.id, "public_id": row.public_id, "reference": row.reference,
            "title": row.title, "summary": row.summary, "status": row.status,
            "priority": row.priority, "payload": row.payload, "updated_at": _iso(row.updated_at),
        } for row in qs[:250]]}
    return None


def theatre_maternity_data(request, slug):
    from operations.models import MaternityEpisode, SurgicalCase
    from enterprise.models import EnterpriseRecord

    org = active_organization(request.user)
    theatre_slugs = {"theatre-calendar", "operating-room-schedule", "surgical-waiting-list", "surgical-case-detail", "team-assignment", "patient-preparation", "consent-checklist", "pre-anaesthetic-assessment", "anaesthesia-chart", "intraoperative-timeline", "vital-sign-graph", "medication-fluid-chart", "blood-product-chart", "instrument-count", "implant-register", "consumable-usage", "operation-note-editor", "recovery-score", "recovery-observation", "post-operative-orders", "specimen-tracking", "sterilization-dashboard", "theatre-turnaround", "theatre-utilization"}
    maternity_slugs = {"antenatal-dashboard", "pregnancy-episode", "antenatal-timeline", "high-risk-pregnancy", "labour-ward-board", "visual-partograph", "delivery-suite", "delivery-team", "caesarean-escalation", "birth-record", "newborn-assessment", "apgar-chart", "mother-baby-linking", "postnatal-monitoring", "immunization-calendar", "vaccination-administration", "growth-chart", "child-health-visit", "nutrition-monitoring", "family-planning"}
    if slug in theatre_slugs:
        qs = SurgicalCase.objects.select_related("patient", "admission", "surgeon", "anaesthetist", "theatre_nurse").order_by("-scheduled_start")
        if org:
            qs = qs.filter(organization=org)
        return {"kind": "theatre_cases", "records": [{
            "id": row.id, "reference": row.case_number, "patient": _user(row.patient),
            "procedure_name": row.procedure_name, "status": row.status, "urgency": row.urgency,
            "theatre_name": row.theatre_name, "scheduled_start": _iso(row.scheduled_start),
            "scheduled_end": _iso(row.scheduled_end), "actual_start": _iso(row.actual_start),
            "actual_end": _iso(row.actual_end), "surgeon": _user(row.surgeon),
            "anaesthetist": _user(row.anaesthetist), "theatre_nurse": _user(row.theatre_nurse),
            "consent_obtained": row.consent_obtained, "complications": row.complications,
        } for row in qs[:300]]}
    if slug in maternity_slugs:
        qs = MaternityEpisode.objects.select_related("patient", "admission", "assigned_midwife", "assigned_clinician").order_by("-created_at")
        if org:
            qs = qs.filter(organization=org)
        records = [{
            "id": row.id, "reference": row.episode_number, "patient": _user(row.patient),
            "gravida": row.gravida, "para": row.para,
            "expected_delivery_date": str(row.expected_delivery_date or ""),
            "gestational_age_weeks": row.gestational_age_weeks,
            "risk_level": row.risk_level, "risk_notes": row.risk_notes,
            "status": row.status, "assigned_midwife": _user(row.assigned_midwife),
            "assigned_clinician": _user(row.assigned_clinician),
            "labour_started_at": _iso(row.labour_started_at), "delivered_at": _iso(row.delivered_at),
            "delivery_method": row.delivery_method, "birth_outcome": row.birth_outcome,
            "newborn_weight_grams": row.newborn_weight_grams,
            "apgar_one_minute": row.apgar_one_minute, "apgar_five_minutes": row.apgar_five_minutes,
        } for row in qs[:300]]
        record_type_map = {
            "visual-partograph": ["partograph"], "newborn-assessment": ["newborn_assessment"],
            "apgar-chart": ["apgar"], "mother-baby-linking": ["mother_baby_link"],
            "immunization-calendar": ["immunization"], "vaccination-administration": ["immunization"],
            "growth-chart": ["growth_measurement"], "nutrition-monitoring": ["nutrition_plan"],
            "family-planning": ["family_planning"],
        }
        extra = EnterpriseRecord.objects.filter(record_type__in=record_type_map.get(slug, []))
        if org:
            extra = extra.filter(organization=org)
        return {"kind": "maternity", "records": records, "observations": [{
            "id": row.id, "public_id": row.public_id, "reference": row.reference,
            "title": row.title, "summary": row.summary, "status": row.status,
            "payload": row.payload, "occurred_at": _iso(row.occurred_at), "updated_at": _iso(row.updated_at),
        } for row in extra[:500]]}
    return None


def facility_data(request, slug):
    from operations.models import Admission, FacilityBed, LeaveRequest, QualityIncident, StaffShift, Ward
    from registry.models import OrganizationLocation, PractitionerCredential
    from workforce.models import Department, StaffMembership

    org = active_organization(request.user)
    if not org:
        return None
    if slug in {"multi-branch-dashboard", "branch-detail"}:
        locations = OrganizationLocation.objects.filter(organization=org)
        return {"kind": "branches", "records": [{
            "id": row.id, "name": row.name, "address": row.address, "district": row.district,
            "latitude": row.latitude, "longitude": row.longitude, "timezone": row.timezone,
            "phone": row.phone, "status": "active" if row.active else "inactive",
        } for row in locations[:200]]}
    if slug in {"department-detail", "room-management", "service-catalogue", "price-lists", "queue-configuration"}:
        departments = Department.objects.filter(organization=org).select_related("location")
        return {"kind": "departments", "records": [{
            "id": row.id, "reference": row.code, "name": row.name,
            "description": row.description, "location": getattr(row.location, "name", None),
            "status": "active" if row.active else "inactive",
        } for row in departments[:250]]}
    if slug in {"visual-bed-map", "ward-detail", "bed-turnover"}:
        beds = FacilityBed.objects.filter(ward__organization=org).select_related("ward").prefetch_related("allocations__admission__patient")
        records = []
        for bed in beds[:500]:
            allocation = bed.allocations.filter(released_at__isnull=True).select_related("admission__patient").first()
            records.append({
                "id": bed.id, "name": bed.label, "ward": bed.ward.name,
                "bed_type": bed.bed_type, "daily_rate": bed.daily_rate,
                "status": bed.status, "patient_name": allocation.admission.patient.display_name if allocation else None,
                "admission_number": allocation.admission.admission_number if allocation else None,
            })
        return {"kind": "beds", "records": records}
    if slug in {"admission-detail", "discharge-clearance"}:
        qs = Admission.objects.filter(organization=org).select_related("patient", "ward", "attending_clinician").prefetch_related("bed_allocations__bed")
        return {"kind": "admissions", "records": [{
            "id": row.id, "reference": row.admission_number, "patient": _user(row.patient),
            "ward": row.ward.name, "bed": _current_bed(row), "status": row.status,
            "attending_clinician": _user(row.attending_clinician), "admitted_at": _iso(row.admitted_at),
            "expected_discharge_at": _iso(row.expected_discharge_at), "discharged_at": _iso(row.discharged_at),
        } for row in qs[:300]]}
    if slug in {"staff-profile", "staff-credential", "staff-onboarding"}:
        memberships = StaffMembership.objects.filter(organization=org).select_related("user", "department")
        return {"kind": "staff", "records": [{
            "id": row.id, "user": _user(row.user), "role": row.role,
            "job_title": row.job_title, "employee_number": row.employee_number,
            "department": getattr(row.department, "name", None), "status": row.status,
            "starts_on": str(row.starts_on or ""), "ends_on": str(row.ends_on or ""),
            "credentials": [{
                "id": credential.id, "type": credential.credential_type,
                "identifier": credential.identifier, "issuer": credential.issuer,
                "expires_on": str(credential.expires_on or ""), "status": credential.status,
            } for credential in PractitionerCredential.objects.filter(practitioner=row.user)[:20]],
        } for row in memberships[:400]]}
    if slug in {"shift-calendar", "leave-calendar", "payroll-integration"}:
        shifts = StaffShift.objects.filter(organization=org).select_related("staff", "department")
        leaves = LeaveRequest.objects.filter(organization=org).select_related("staff", "reviewed_by")
        return {"kind": "workforce_calendar", "shifts": [{
            "id": row.id, "staff": _user(row.staff), "department": getattr(row.department, "name", None),
            "shift_type": row.shift_type, "starts_at": _iso(row.starts_at), "ends_at": _iso(row.ends_at),
            "status": row.status, "location": row.location,
        } for row in shifts[:500]], "leaves": [{
            "id": row.id, "staff": _user(row.staff), "leave_type": row.leave_type,
            "starts_on": str(row.starts_on), "ends_on": str(row.ends_on), "status": row.status,
            "reviewed_by": _user(row.reviewed_by),
        } for row in leaves[:300]]}
    if slug in {"incident-detail", "corrective-action", "infection-control", "complaint-detail", "regulatory-reporting"}:
        incidents = QualityIncident.objects.filter(organization=org).select_related("patient", "reported_by", "assigned_to")
        return {"kind": "quality_incidents", "records": [{
            "id": row.id, "reference": row.incident_number, "patient": _user(row.patient),
            "category": row.category, "severity": row.severity, "title": row.title,
            "description": row.description, "immediate_actions": row.immediate_actions,
            "root_cause": row.root_cause, "corrective_actions": row.corrective_actions,
            "status": row.status, "occurred_at": _iso(row.occurred_at),
            "reported_by": _user(row.reported_by), "assigned_to": _user(row.assigned_to),
        } for row in incidents[:300]]}
    return None


def insurance_data(request, slug):
    from services.models import (InsuranceBenefitRule, InsuranceClaim, InsuranceEligibilityCheck,
        InsurancePolicy, InsurancePreauthorization, InsuranceRemittance, PatientCoverage)
    from enterprise.models import PayerContract, TariffSchedule

    provider = request.user if active_role(request.user) == "insurance" else _org_owner_account(request.user)
    if not provider:
        return None
    if slug in {"member-directory", "member-profile", "eligibility-detail"}:
        coverages = PatientCoverage.objects.filter(provider=provider).select_related("patient", "policy")
        return {"kind": "members", "records": [{
            "id": row.id, "patient": _user(row.patient), "member_id": row.member_id,
            "policy": row.policy.name, "active": row.active, "effective_from": str(row.effective_from),
            "expires_on": str(row.expires_on or ""), "dependant_code": row.dependant_code,
            "employer_or_group": row.employer_or_group, "verified_at": _iso(row.verified_at),
        } for row in coverages[:500]]}
    if slug in {"plan-designer", "benefit-comparison"}:
        policies = InsurancePolicy.objects.filter(provider=provider).prefetch_related("benefit_rules")
        return {"kind": "insurance_plans", "records": [{
            "id": row.id, "name": row.name, "coverage_percent": row.coverage_percent,
            "premium": row.premium, "annual_limit": row.annual_limit,
            "deductible": row.deductible, "copay_percent": row.copay_percent,
            "copay_fixed": row.copay_fixed, "active": row.active,
            "requires_preauthorization": row.requires_preauthorization,
            "exclusions": row.exclusions, "rules": [{
                "service_code": rule.service_code, "category": rule.service_category,
                "coverage_percent": rule.coverage_percent, "annual_limit": rule.annual_limit,
                "per_visit_limit": rule.per_visit_limit, "excluded": rule.excluded,
            } for rule in row.benefit_rules.all()],
        } for row in policies[:200]]}
    if slug in {"preauthorization-workbench", "medical-review"}:
        qs = InsurancePreauthorization.objects.filter(provider=provider).select_related("patient", "policy", "reviewed_by")
        return {"kind": "preauthorizations", "records": [{
            "id": row.id, "reference": row.authorization_number, "patient": _user(row.patient),
            "service_code": row.service_code, "service_name": row.service_name,
            "clinical_indication": row.clinical_indication, "diagnosis_code": row.diagnosis_code,
            "requested_amount": row.requested_amount, "approved_amount": row.approved_amount,
            "status": row.status, "decision_reason": row.decision_reason,
            "reviewed_by": _user(row.reviewed_by), "valid_until": _iso(row.valid_until),
        } for row in qs[:400]]}
    if slug in {"claim-detail", "claim-line-adjudication", "diagnosis-procedure-coding", "document-review", "claim-query", "appeal-review", "fraud-investigation", "claims-ageing", "loss-ratio", "utilization-analytics"}:
        qs = InsuranceClaim.objects.filter(provider=provider).select_related("patient", "policy", "reviewed_by").prefetch_related("items")
        return {"kind": "claims", "records": [{
            "id": row.id, "reference": row.claim_number, "patient": _user(row.patient),
            "policy": getattr(row.policy, "name", None), "status": row.status,
            "amount": row.amount, "approved_amount": row.approved_amount,
            "patient_responsibility": row.patient_responsibility,
            "diagnosis_code": row.diagnosis_code, "clinical_summary": row.clinical_summary,
            "decision_reason": row.decision_reason, "reviewed_by": _user(row.reviewed_by),
            "submitted_at": _iso(row.submitted_at), "reviewed_at": _iso(row.reviewed_at),
            "payload": {"lines": [{
                "id": item.id, "service": item.description, "service_code": item.service_code,
                "claimed": item.requested_amount, "allowed": item.approved_amount,
                "decision": item.status, "reason": item.reason,
            } for item in row.items.all()]},
        } for row in qs[:400]]}
    if slug in {"remittance-import", "settlement-reconciliation", "provider-payment"}:
        qs = InsuranceRemittance.objects.filter(provider=provider).select_related("claim", "created_by")
        return {"kind": "remittances", "records": [{
            "id": row.id, "reference": row.remittance_number,
            "claim": row.claim.claim_number, "paid_amount": row.paid_amount,
            "payment_reference": row.payment_reference, "paid_on": str(row.paid_on),
            "notes": row.notes, "created_by": _user(row.created_by), "status": "paid",
        } for row in qs[:400]]}
    if slug in {"provider-network", "provider-contract", "tariff-editor"}:
        contracts = PayerContract.objects.filter(payer=active_organization(request.user)).select_related("provider", "tariff") if active_organization(request.user) else PayerContract.objects.none()
        tariffs = TariffSchedule.objects.filter(payer=active_organization(request.user)) if active_organization(request.user) else TariffSchedule.objects.none()
        return {"kind": "contracts", "contracts": [{
            "id": row.id, "reference": row.contract_number, "provider": row.provider.legal_name,
            "status": row.status, "starts_on": str(row.starts_on), "ends_on": str(row.ends_on or ""),
            "tariff": getattr(row.tariff, "name", None),
        } for row in contracts[:250]], "tariffs": [{
            "id": row.id, "name": row.name, "currency": row.currency,
            "valid_from": str(row.valid_from), "valid_to": str(row.valid_to or ""),
            "items": row.items, "status": "active" if row.active else "inactive",
        } for row in tariffs[:250]]}
    return None


def admin_data(request, slug):
    """Narrowly scoped administrative data; no role receives blanket clinical data."""
    from accounts.models import SecurityEvent, User
    from enterprise.access import (can_manage_integrations, can_manage_operations,
        can_manage_platform, can_review_compliance, can_review_clinical_safety, can_view_system_health)
    from enterprise.models import (ContentEntry, DeadLetterEvent, EventDelivery, FeatureConfiguration,
        IntegrationEndpoint, ReplayRequest, SecurityOperation, VerificationAutomation)
    from governance.models import AuditEvent, PrivilegedAccessGrant

    user = request.user
    if slug in {"user-detail", "account-activity", "session-management", "role-matrix", "permission-comparison", "organization-detail", "branch-detail", "professional-detail", "subscription-detail", "localization", "maintenance-mode", "feature-flags"}:
        if not can_manage_platform(user):
            return {"kind": "administration", "records": [], "restricted": True, "message": "Platform-super-administrator access is required."}
        users = User.objects.order_by("-date_joined")[:500]
        return {"kind": "users", "records": [{
            "id": row.id, "name": row.display_name, "email": row.email, "phone": row.phone,
            "registration_role": row.role, "active_role": _active_role_label(row),
            "is_active": row.is_active, "is_verified": row.is_verified,
            "mfa_enabled": row.mfa_enabled, "locked_until": _iso(row.locked_until),
            "last_login": _iso(row.last_login), "date_joined": _iso(row.date_joined),
            "status": "locked" if row.locked_until and row.locked_until > timezone.now() else ("active" if row.is_active else "inactive"),
        } for row in users]}
    if slug in {"verification-case", "licence-viewer", "ocr-comparison", "verification-timeline", "credential-renewals"}:
        if not (can_manage_platform(user) or can_review_compliance(user)):
            return {"kind": "verification", "records": [], "restricted": True}
        qs = VerificationAutomation.objects.select_related("credential__practitioner", "organization", "reviewed_by").order_by("-created_at")
        return {"kind": "verification", "records": [{
            "id": row.id, "reference": f"VER-{row.id}",
            "title": getattr(getattr(row, "credential", None), "title", "Credential verification"),
            "subject": _user(getattr(getattr(row, "credential", None), "practitioner", None)),
            "organization": getattr(row.organization, "legal_name", None), "status": row.status,
            "summary": row.recommendation, "payload": {
                "declared": {"identifier": getattr(getattr(row, "credential", None), "identifier", ""), "issuer": getattr(getattr(row, "credential", None), "issuer", "")},
                "extracted": row.extracted_fields, "confidence": row.match_score,
                "document_quality_score": row.document_quality_score, "fraud_score": row.fraud_score,
                "flags": row.flags, "regulator_response": row.regulator_response,
            }, "created_at": _iso(row.created_at), "updated_at": _iso(row.completed_at),
        } for row in qs[:400]]}
    if slug in {"integration-detail", "event-delivery", "dead-letter", "event-replay", "worker-health", "system-metrics", "backup-restore"}:
        if not (can_manage_integrations(user) or can_view_system_health(user)):
            return {"kind": "operations", "records": [], "restricted": True}
        endpoints = IntegrationEndpoint.objects.all()[:200] if can_manage_integrations(user) else IntegrationEndpoint.objects.none()
        deliveries = EventDelivery.objects.select_related("endpoint", "schema").order_by("-created_at")[:300] if can_manage_integrations(user) else EventDelivery.objects.none()
        dead = DeadLetterEvent.objects.select_related("delivery__endpoint", "resolved_by").order_by("-quarantined_at")[:200] if can_manage_integrations(user) else DeadLetterEvent.objects.none()
        security_ops = SecurityOperation.objects.order_by("-created_at")[:200]
        return {"kind": "platform_operations", "records": [{
            "id": row.id, "reference": row.name, "title": row.name,
            "type": row.endpoint_type, "status": row.health_status,
            "base_url": row.base_url, "topic": row.topic,
            "active": row.active, "last_health_check_at": _iso(row.last_health_check_at),
        } for row in endpoints], "deliveries": [{
            "id": row.id, "endpoint": row.endpoint.name, "schema": getattr(row.schema, "name", None),
            "status": row.status, "attempt_count": row.attempt_count,
            "response_code": row.response_code, "response_body": row.response_body,
            "created_at": _iso(row.created_at), "delivered_at": _iso(row.delivered_at),
        } for row in deliveries], "dead_letters": [{
            "id": row.id, "endpoint": row.delivery.endpoint.name,
            "reason": row.reason, "quarantined_at": _iso(row.quarantined_at),
            "resolved_at": _iso(row.resolved_at), "resolution": row.resolution,
        } for row in dead], "security_operations": [{
            "id": row.id, "reference": row.reference, "operation_type": row.operation_type,
            "status": row.status, "severity": row.severity, "title": row.title,
            "description": row.description, "started_at": _iso(row.started_at),
            "completed_at": _iso(row.completed_at), "next_due_at": _iso(row.next_due_at),
        } for row in security_ops]}
    if slug in {"audit-explorer", "security-incident", "data-export-centre", "retention-controls", "regulatory-reporting"}:
        if not (can_review_compliance(user) or can_review_clinical_safety(user)):
            return {"kind": "compliance", "records": [], "restricted": True}
        audits = AuditEvent.objects.select_related("actor", "patient").order_by("-created_at")[:500]
        grants = PrivilegedAccessGrant.objects.select_related("requester", "approved_by", "patient").order_by("-requested_at")[:200]
        return {"kind": "compliance", "records": [{
            "id": row.id, "actor": _user(row.actor), "patient": _user(row.patient),
            "action": row.action, "resource_type": row.resource_type, "resource_id": row.resource_id,
            "purpose": row.purpose, "decision": row.decision, "reason": row.reason,
            "occurred_at": _iso(row.created_at), "metadata": row.metadata,
        } for row in audits], "privileged_access": [{
            "id": row.id, "requester": _user(row.requester), "patient": _user(row.patient),
            "purpose": row.purpose, "reason": row.reason, "scopes": row.scopes,
            "status": row.status, "approved_by": _user(row.approved_by),
            "starts_at": _iso(row.approved_at), "expires_at": _iso(row.expires_at),
        } for row in grants]}
    if slug in {"cms-editor", "template-editor", "notification-monitor"}:
        if not can_manage_operations(user):
            return {"kind": "content_operations", "records": [], "restricted": True}
        content = ContentEntry.objects.order_by("-updated_at")[:300]
        return {"kind": "content", "records": [{
            "id": row.id, "reference": row.slug, "title": row.title,
            "content_type": row.content_type, "locale": row.locale,
            "audience": row.audience, "placement": row.placement,
            "status": row.status, "version": row.version,
            "starts_at": _iso(row.starts_at), "ends_at": _iso(row.ends_at),
            "updated_at": _iso(row.updated_at),
        } for row in content]}
    return None

def page_operational_data(request, slug):
    role = request_role(request)
    setattr(request.user, "_active_role", role)
    loaders = []
    if role == "patient":
        loaders.append(patient_data)
    if role in {"doctor", "clinical_officer", "dentist", "physiotherapist", "nutritionist", "psychologist", "medical_director"}:
        loaders.append(clinical_data)
    if role in {"nurse", "midwife", "theatre_nurse"}:
        loaders.extend([nursing_data, theatre_maternity_data])
    if role == "receptionist":
        loaders.append(reception_data)
    if role == "records_officer":
        loaders.append(records_data)
    if role in {"cashier", "accountant", "finance_manager"}:
        loaders.append(finance_data)
    if role in {"pharmacist", "storekeeper", "pharmacy"}:
        loaders.append(pharmacy_data)
    if role in {"lab_technician", "lab"}:
        loaders.append(laboratory_data)
    if role in {"paramedic", "ambulance_dispatcher"}:
        loaders.append(emergency_data)
    if role in {"anaesthetist", "theatre_nurse"}:
        loaders.append(theatre_maternity_data)
    if role in {"facility_manager", "procurement_officer", "quality_officer", "hr_officer", "hospital"}:
        loaders.extend([facility_data, theatre_maternity_data, emergency_data])
    if role in {"insurance", "insurance_officer", "claims_reviewer"}:
        loaders.append(insurance_data)
    if role in {"admin", "platform_super_admin", "operations_admin", "compliance_admin", "clinical_safety_admin", "it_support", "compliance_officer"}:
        loaders.append(admin_data)
    for loader in loaders:
        data = loader(request, slug)
        if data is not None:
            data["configured"] = True
            data["active_role"] = role
            data["organization"] = getattr(active_organization(request.user), "legal_name", None)
            data["generated_at"] = timezone.now()
            return data
    definition = definition_for(slug) or {}
    record_types = list(definition.get("recordTypes") or [])
    if record_types:
        from enterprise.models import EnterpriseRecord

        records = record_queryset_for(
            request.user,
            EnterpriseRecord.objects.select_related(
                "organization", "location", "department", "patient", "admission",
                "appointment", "owner", "assigned_to",
            ).filter(record_type__in=record_types),
        )
        return {
            "configured": True,
            "active_role": role,
            "organization": getattr(active_organization(request.user), "legal_name", None),
            "kind": "enterprise_records",
            "canonical_source": "enterprise_record",
            "page_mode": definition.get("page_mode"),
            "records": [{
                "id": row.id, "public_id": str(row.public_id), "reference": row.reference,
                "title": row.title, "summary": row.summary, "domain": row.domain,
                "record_type": row.record_type, "status": row.status, "priority": row.priority,
                "patient": _user(row.patient), "assigned_to": _user(row.assigned_to),
                "admission_id": row.admission_id, "appointment_id": row.appointment_id,
                "payload": row.payload, "occurred_at": _iso(row.occurred_at),
                "due_at": _iso(row.due_at), "completed_at": _iso(row.completed_at),
                "updated_at": _iso(row.updated_at),
            } for row in records[:500]],
            "generated_at": timezone.now(),
        }

    adapter = definition.get("adapter")
    if adapter in {
        "operational_action", "front_desk_operation", "facility_operation",
        "insurance_operation", "radiology_operation",
    }:
        from .models import OperationalAction
        from .services import workflow_queryset

        accessible_case_ids = workflow_queryset(request.user, slug).values("id")
        actions = OperationalAction.objects.select_related(
            "workflow_case", "patient", "subject_user", "appointment", "admission",
            "invoice", "created_by", "approved_by", "executed_by",
        ).filter(workflow_case_id__in=accessible_case_ids)
        return {
            "configured": True,
            "active_role": role,
            "organization": getattr(active_organization(request.user), "legal_name", None),
            "kind": "operational_actions",
            "canonical_source": "operational_action",
            "page_mode": definition.get("page_mode"),
            "records": [{
                "id": row.id, "public_id": str(row.public_id),
                "reference": row.workflow_case.reference, "title": row.workflow_case.title,
                "summary": row.workflow_case.summary, "page_slug": row.page_slug,
                "domain": row.domain, "operation_code": row.operation_code,
                "status": row.state, "patient": _user(row.patient),
                "payload": row.payload, "result": row.result, "effect_log": row.effect_log,
                "effect_reference_type": row.effect_reference_type,
                "effect_reference_id": row.effect_reference_id,
                "requires_approval": row.requires_approval,
                "approved_by": _user(row.approved_by), "approved_at": _iso(row.approved_at),
                "executed_by": _user(row.executed_by), "executed_at": _iso(row.executed_at),
                "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at),
            } for row in actions[:500]],
            "generated_at": timezone.now(),
        }

    # A queue/reference page is intentionally a scoped workflow view rather than
    # a fake domain table. It is labelled clearly so the UI does not imply that
    # a separate clinical record exists.
    from .services import workflow_queryset
    queue = workflow_queryset(request.user, slug)
    return {
        "configured": True,
        "active_role": role,
        "organization": getattr(active_organization(request.user), "legal_name", None),
        "kind": "work_queue" if definition.get("page_mode") == "work_queue" else "reference_view",
        "canonical_source": "workflow_queue",
        "page_mode": definition.get("page_mode"),
        "read_only": definition.get("create_allowed") is False,
        "records": [{
            "id": row.id, "public_id": str(row.public_id), "reference": row.reference,
            "title": row.title, "summary": row.summary, "status": row.status,
            "priority": row.priority, "patient": _user(row.patient),
            "assigned_to": _user(row.assigned_to), "data": row.data, "result": row.result,
            "due_at": _iso(row.due_at), "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        } for row in queue[:500]],
        "message": "This page is an explicitly scoped work queue or reference view. Transactions are completed through the linked canonical workflow actions.",
        "generated_at": timezone.now(),
    }

