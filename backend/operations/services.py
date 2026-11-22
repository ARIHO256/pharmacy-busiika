"""Transactional workflows. No workflow mutates accounting/payment records."""
import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from governance.services import audit
from interoperability.services import emit_event
from registry.models import Organization
from services.models import Bed, Medicine, PatientCoverage

from . import models as m
from .access import clinician_at, patient_is_valid, require_organization, require_role


def event(record, actor, action, **data):
    organization = getattr(record, "organization", None)
    m.WorkflowEvent.objects.create(
        organization=organization, resource_type=record.__class__.__name__,
        resource_id=record.pk, actor=actor, action=action, data=data,
    )
    audit(actor=actor, action=f"operations.{action}", resource=record,
          patient=getattr(record, "patient", None), metadata=data, purpose="operations")
    emit_event(f"operations.{action}", record, {"id": record.pk, **data}, actor=actor,
               patient=getattr(record, "patient", None))


def expect_version(record, version):
    if version is None or version != record.version:
        raise ValidationError({"version": "The record changed. Refresh it and submit its current version."}, code="conflict")


def available_bed(organization, bed_id):
    bed = Bed.objects.select_for_update().filter(pk=bed_id, hospital_id=organization.owner_id).first()
    if not bed or bed.is_occupied or m.Admission.objects.filter(bed=bed, status="admitted").exists():
        raise ValidationError({"bed": "Bed is unavailable or belongs to another facility."})
    return bed


@transaction.atomic
def admit(*, actor, organization, patient, attending_doctor, bed=None, **fields):
    require_organization(actor, organization.pk, {"hospital", "doctor", "nurse", "receptionist", "facility_manager"})
    patient_is_valid(patient)
    if organization.organization_type not in {"hospital", "clinic"}:
        raise ValidationError("Admissions require a hospital or clinic.")
    clinician_at(attending_doctor, organization)
    if attending_doctor.role != "doctor":
        raise ValidationError({"attending_doctor": "A verified doctor is required."})
    # Serialize admissions for the same patient, including attempts at other facilities.
    type(patient).objects.select_for_update().get(pk=patient.pk)
    if m.Admission.objects.filter(patient=patient, status="admitted").exists():
        raise ValidationError("Patient already has an active admission.")
    if bed:
        bed = available_bed(organization, bed.pk)
        bed.is_occupied = True
        bed.save(update_fields=["is_occupied"])
    record = m.Admission.objects.create(organization=organization, created_by=actor,
                                       patient=patient, attending_doctor=attending_doctor, bed=bed, **fields)
    event(record, actor, "admission.created")
    return record


@transaction.atomic
def admission_action(record, actor, action, *, version, bed=None, summary="", follow_up=""):
    record = m.Admission.objects.select_for_update().get(pk=record.pk)
    require_organization(actor, record.organization_id, {"doctor", "nurse", "hospital", "facility_manager"})
    expect_version(record, version)
    if record.status != "admitted":
        raise ValidationError("Discharged admissions cannot be changed.")
    if action == "transfer":
        new_bed = available_bed(record.organization, bed)
        if record.bed_id:
            Bed.objects.filter(pk=record.bed_id).update(is_occupied=False)
        new_bed.is_occupied = True
        new_bed.save(update_fields=["is_occupied"])
        record.bed = new_bed
    elif action == "discharge":
        require_role(actor, {"doctor"})
        if not summary.strip():
            raise ValidationError({"summary": "A signed discharge summary is required."})
        record.status = "discharged"
        record.discharged_at = timezone.now()
        record.discharge_summary = summary
        record.follow_up = follow_up
        if record.bed_id:
            Bed.objects.filter(pk=record.bed_id).update(is_occupied=False)
        record.medication_schedules.filter(status="scheduled").update(status="cancelled", notes="Admission discharged")
    else:
        raise ValidationError("Unknown admission action.")
    record.version += 1
    record.save()
    event(record, actor, f"admission.{action}", version=record.version)
    return record


@transaction.atomic
def record_dose(record, actor, status, notes):
    record = m.MedicationSchedule.objects.select_for_update().get(pk=record.pk)
    require_organization(actor, record.organization_id, {"doctor", "nurse"})
    admission = m.Admission.objects.select_for_update().get(pk=record.admission_id)
    if admission.status != "admitted" or record.status != "scheduled":
        raise ValidationError("Dose is already resolved or admission is closed.")
    if status not in {"given", "withheld", "refused", "cancelled"}:
        raise ValidationError({"status": "Invalid administration status."})
    if status != "given" and not notes.strip():
        raise ValidationError({"notes": "A reason is required."})
    if status == "given" and record.due_at > timezone.now() + timedelta(minutes=30):
        raise ValidationError("Dose is not yet due.")
    if status == "given" and (record.prescription.status not in {"issued", "partially_dispensed", "dispensed"} or record.prescription.expires_at <= timezone.now()):
        raise ValidationError("Prescription is no longer valid.")
    record.status, record.notes = status, notes
    record.administered_by, record.administered_at = actor, timezone.now()
    record.save()
    event(record, actor, "medication.resolved", status=status)
    return record


@transaction.atomic
def procedure_action(record, actor, status, notes):
    record = m.ProcedureBooking.objects.select_for_update().get(pk=record.pk)
    require_organization(actor, record.organization_id, {"doctor", "facility_manager"} if status == "cancelled" else {"doctor"})
    transitions = {"scheduled": {"in_progress", "cancelled"}, "in_progress": {"completed"}}
    if status not in transitions.get(record.status, set()):
        raise ValidationError("Invalid procedure transition.")
    if status in {"completed", "cancelled"} and not notes.strip():
        raise ValidationError("Procedure outcome or cancellation reason is required.")
    record.status, record.notes = status, notes
    record.save()
    event(record, actor, "procedure.transition", status=status)
    return record


def refresh_stock(medicine):
    """The legacy stock field mirrors sellable batch stock once batch tracking starts."""
    total = m.MedicineBatch.objects.filter(medicine=medicine, status="available",
                                           expires_on__gt=timezone.localdate()).aggregate(total=Sum("quantity"))["total"] or 0
    Medicine.objects.filter(pk=medicine.pk).update(stock=total)


@transaction.atomic
def move_stock(batch, actor, *, quantity, kind, reason, reference, patient=None, witness=None, prescription_item=None, pharmacy_order=None):
    # Medicine first, then batches: consistent lock order with checkout.
    medicine = Medicine.objects.select_for_update().get(pk=batch.medicine_id)
    batch = m.MedicineBatch.objects.select_for_update().get(pk=batch.pk)
    require_organization(actor, batch.organization_id, {"pharmacy", "pharmacist", "storekeeper", "facility_manager"})
    previous = m.StockMovement.objects.filter(reference=reference).first()
    if previous:
        if (previous.batch_id, previous.quantity, previous.kind, previous.patient_id, previous.actor_id, previous.reason, previous.witness_id, previous.prescription_item_id, previous.pharmacy_order_id) != (batch.pk, quantity, kind, getattr(patient, "pk", None), actor.pk, reason, getattr(witness, "pk", None), getattr(prescription_item, "pk", None), getattr(pharmacy_order, "pk", None)):
            raise ValidationError("Idempotency reference was used for different movement data.")
        return previous
    if not reason.strip() or quantity == 0:
        raise ValidationError("A non-zero quantity and reason are required.")
    if kind in {"received", "returned"} and quantity < 0 or kind in {"dispensed", "destroyed"} and quantity > 0:
        raise ValidationError("Quantity sign does not match movement kind.")
    if kind not in {"received", "returned", "dispensed", "destroyed", "adjusted"}:
        raise ValidationError("Unknown stock movement kind.")
    if kind == "dispensed" and (medicine.sale_type != Medicine.SaleType.OTC or batch.controlled) and not pharmacy_order:
        raise ValidationError("This product requires dispensing through a linked pharmacy prescription order.")
    if kind == "dispensed" and medicine.sale_type == Medicine.SaleType.CONTROLLED and not batch.controlled:
        raise ValidationError("Controlled products require a controlled batch.")
    if kind == "dispensed" and (batch.status != "available" or batch.expires_on <= timezone.localdate()):
        raise ValidationError("Expired, quarantined or recalled stock cannot be dispensed.")
    if batch.quantity + quantity < 0:
        raise ValidationError("Insufficient batch stock.")
    if patient:
        patient_is_valid(patient)
    if batch.controlled:
        require_role(actor, {"pharmacist"})
        if witness is None or witness.pk == actor.pk:
            raise ValidationError("Controlled stock requires an independent verified witness.")
        require_organization(witness, batch.organization_id, {"pharmacist", "doctor"})
        if kind == "dispensed" and not prescription_item:
            raise ValidationError("Controlled dispensing requires a signed prescription item.")
    if prescription_item:
        if not pharmacy_order:
            raise ValidationError("Dispense prescription items through the linked pharmacy order.")
        from prescriptions.models import Prescription, PrescriptionItem
        require_role(actor, {"pharmacist"})
        prescription = Prescription.objects.select_for_update().get(pk=prescription_item.prescription_id)
        prescription_item = PrescriptionItem.objects.select_for_update().get(pk=prescription_item.pk)
        if kind != "dispensed" or not prescription.signed_at or patient is None or prescription.patient_id != patient.pk or prescription.status not in {"issued", "partially_dispensed"} or prescription.expires_at <= timezone.now():
            raise ValidationError("A valid prescription for the dispensing patient is required.")
        replacement = None
        if pharmacy_order:
            replacement = pharmacy_order.substitutions.filter(
                item=prescription_item, status="approved", prescription_version=prescription.version,
            ).first()
        matches = (replacement.replacement_id == medicine.pk and not batch.controlled
                   and medicine.sale_type in {"otc", "prescription"}) if replacement else (
                       prescription_item.medicine_name.strip().casefold() == medicine.name.strip().casefold()
                   )
        if not matches or prescription_item.dispensed_quantity - quantity > prescription_item.quantity:
            raise ValidationError("Medicine does not match or the prescription quantity would be exceeded.")
        prescription_item.dispensed_quantity -= quantity
        prescription_item.save(update_fields=["dispensed_quantity"])
        prescription.status = "dispensed" if not prescription.items.filter(dispensed_quantity__lt=F("quantity")).exists() else "partially_dispensed"
        prescription.save(update_fields=["status"])
    batch.quantity += quantity
    batch.save(update_fields=["quantity", "updated_at"])
    movement = m.StockMovement.objects.create(batch=batch, quantity=quantity, balance=batch.quantity,
        kind=kind, reason=reason, reference=reference, patient=patient, actor=actor, witness=witness, prescription_item=prescription_item, pharmacy_order=pharmacy_order)
    refresh_stock(medicine)
    event(batch, actor, "stock.moved", movement_id=movement.pk, quantity=quantity, kind=kind)
    return movement


@transaction.atomic
def reverse_unhanded_dispense(original, actor, *, reason, witness=None):
    from prescriptions.models import Prescription, PrescriptionItem

    require_role(actor, {"pharmacist"})
    medicine = Medicine.objects.select_for_update().get(pk=original.batch.medicine_id)
    batch = m.MedicineBatch.objects.select_for_update().get(pk=original.batch_id)
    require_organization(actor, batch.organization_id)
    previous = m.StockMovement.objects.filter(reversal_of=original).first()
    if previous:
        return previous
    if batch.controlled:
        if witness is None or witness.pk == actor.pk:
            raise ValidationError("Controlled stock requires an independent verified witness.")
        require_organization(witness, batch.organization_id, {"pharmacist", "doctor"})
    item = original.prescription_item
    prescription = Prescription.objects.select_for_update().get(pk=item.prescription_id)
    item = PrescriptionItem.objects.select_for_update().get(pk=item.pk)
    quantity = -original.quantity
    if quantity <= 0 or item.dispensed_quantity < quantity or prescription.status not in {"partially_dispensed", "dispensed"}:
        raise ValidationError("This movement cannot be reversed against the current prescription.")
    item.dispensed_quantity -= quantity
    item.save(update_fields=["dispensed_quantity"])
    prescription.status = "partially_dispensed" if prescription.items.filter(dispensed_quantity__gt=0).exists() else "issued"
    prescription.save(update_fields=["status"])
    batch.quantity += quantity
    batch.save(update_fields=["quantity", "updated_at"])
    reversal = m.StockMovement.objects.create(
        batch=batch, quantity=quantity, balance=batch.quantity, kind="returned", reason=reason,
        patient=original.patient, actor=actor, witness=witness, prescription_item=item,
        pharmacy_order=original.pharmacy_order, reversal_of=original,
    )
    refresh_stock(medicine)
    event(batch, actor, "stock.dispense_reversed", movement_id=reversal.pk, original_id=original.pk)
    return reversal



@transaction.atomic
def batch_action(batch, actor, action, *, temperature=None, reason=""):
    medicine = Medicine.objects.select_for_update().get(pk=batch.medicine_id)
    batch = m.MedicineBatch.objects.select_for_update().get(pk=batch.pk)
    require_organization(actor, batch.organization_id, {"pharmacy", "pharmacist", "storekeeper", "facility_manager"})
    if action == "temperature":
        excursion = (batch.min_temperature is not None and temperature < batch.min_temperature) or (batch.max_temperature is not None and temperature > batch.max_temperature)
        m.TemperatureReading.objects.create(batch=batch, temperature=temperature, excursion=excursion, recorded_by=actor)
        if excursion and batch.status == "available":
            batch.status = "quarantined"
    elif action in {"recall", "quarantine", "release"}:
        if not reason.strip():
            raise ValidationError("A reason is required.")
        if batch.status == "recalled":
            raise ValidationError("A recalled batch cannot be returned to circulation.")
        if action == "release":
            require_role(actor, {"pharmacist"})
            if batch.status != "quarantined" or batch.expires_on <= timezone.localdate():
                raise ValidationError("Only unexpired quarantined batches can be released.")
        batch.status = {"recall": "recalled", "quarantine": "quarantined", "release": "available"}[action]
    else:
        raise ValidationError("Unknown batch action.")
    batch.save()
    refresh_stock(medicine)
    event(batch, actor, f"batch.{action}", reason=reason)
    if action == "recall":
        from .pharmacy_safety_views import create_recall_contacts
        create_recall_contacts(batch, actor)
    return batch


def online_orderable_batches(medicine):
    if medicine.sale_type != Medicine.SaleType.OTC or medicine.batches.filter(controlled=True).exists():
        return medicine.batches.none()
    return medicine.batches.filter(
        organization__owner=medicine.pharmacy_id,
        organization__active=True,
        organization__status="verified",
        status="available",
        expires_on__gt=timezone.localdate(),
    ).filter(
        Q(organization__parent_facility__isnull=True)
        | Q(organization__parent_facility__active=True, organization__parent_facility__status="verified"),
    )


@transaction.atomic
def allocate_order_stock(medicine, quantity, actor, reference, *, organization=None):
    """Allocate eligible OTC stock by earliest expiry inside the sale transaction."""
    medicine = Medicine.objects.select_for_update().get(pk=medicine.pk)
    if quantity <= 0:
        raise ValidationError("Quantity must be positive.")
    if medicine.sale_type != Medicine.SaleType.OTC or medicine.batches.filter(controlled=True).exists():
        raise ValidationError("Only classified over-the-counter medicines can be ordered from the store.")
    if not medicine.batches.exists():
        raise ValidationError("Online orders require traceable batch stock.")
    eligible = online_orderable_batches(medicine)
    if organization:
        eligible = eligible.filter(organization=organization)
    batches = list(eligible.select_for_update(of=("self",)).order_by("expires_on", "id"))
    if sum(batch.quantity for batch in batches) < quantity:
        raise ValidationError(f"Insufficient unexpired stock for {medicine.name}.")
    remaining = quantity
    for batch in batches:
        amount = min(remaining, batch.quantity)
        if amount:
            batch.quantity -= amount
            batch.save(update_fields=["quantity", "updated_at"])
            m.StockMovement.objects.create(batch=batch, quantity=-amount, balance=batch.quantity,
                kind="dispensed", reason=f"Sale order {reference}", actor=actor,
                patient=actor if organization is None else None, order_id=reference)
            remaining -= amount
        if not remaining:
            break
    refresh_stock(medicine)


@transaction.atomic
def restore_order_stock(order, actor):
    items = list(order.items.order_by("medicine_id"))
    medicines = {med.pk: med for med in Medicine.objects.select_for_update().filter(pk__in=[item.medicine_id for item in items if item.medicine_id]).order_by("pk")}
    for item in items:
        if not item.medicine_id:
            continue
        medicine = medicines[item.medicine_id]
        movements = list(m.StockMovement.objects.filter(order=order, batch__medicine=medicine, kind="dispensed").select_related("batch").order_by("batch_id"))
        if movements:
            for movement in movements:
                batch = m.MedicineBatch.objects.select_for_update().get(pk=movement.batch_id)
                batch.quantity -= movement.quantity
                batch.save(update_fields=["quantity", "updated_at"])
                m.StockMovement.objects.create(batch=batch, quantity=-movement.quantity, balance=batch.quantity,
                    kind="returned", reason=f"Cancelled online order {order.pk}", order=order, actor=actor, patient=order.patient)
            refresh_stock(medicine)
        elif medicine.batches.exists():
            raise ValidationError("This legacy order needs a documented stock reconciliation before cancellation.")
        else:
            medicine.stock += item.qty
            medicine.save(update_fields=["stock"])


@transaction.atomic
def referral_action(route, actor, status, *, version, outcome="", scheduled_at=None, assigned_to=None):
    route = m.ReferralRoute.objects.select_for_update().select_related("referral").get(pk=route.pk)
    referral = type(route.referral).objects.select_for_update().get(pk=route.referral_id)
    expect_version(route, version)
    if status == "cancelled":
        if actor.pk != referral.referring_provider_id and actor.role != "admin":
            raise PermissionDenied("Only the referring clinician can cancel this referral.")
    else:
        require_organization(actor, route.organization_id, {"doctor"})
    transitions = {"sent": {"accepted", "declined", "cancelled"}, "accepted": {"in_progress", "cancelled"}, "in_progress": {"completed", "cancelled"}}
    if status not in transitions.get(referral.status, set()):
        raise ValidationError("Invalid referral transition.")
    if referral.expires_at and referral.expires_at <= timezone.now() and status != "cancelled":
        raise ValidationError("Referral has expired.")
    if status in {"completed", "declined", "cancelled"} and not outcome.strip():
        raise ValidationError("An outcome or reason is required.")
    if assigned_to:
        require_organization(assigned_to, route.organization_id, {"doctor"})
        route.assigned_to = assigned_to
    if scheduled_at:
        if scheduled_at < timezone.now():
            raise ValidationError("Schedule must be in the future.")
        route.scheduled_at = scheduled_at
    referral.status = status
    referral.save(update_fields=["status", "updated_at"])
    route.outcome = outcome
    route.version += 1
    route.save()
    event(route, actor, "referral.transition", status=status, version=route.version)
    return route


@transaction.atomic
def decide_authorization(record, actor, status, approved_amount, reason):
    record = m.Preauthorization.objects.select_for_update().get(pk=record.pk)
    require_organization(actor, record.organization_id, {"insurance", "insurance_officer"})
    if record.status != "requested" or status not in {"approved", "rejected"}:
        raise ValidationError("Authorization is already decided or status is invalid.")
    if record.expires_on < timezone.localdate() or not record.coverage.active:
        raise ValidationError("Coverage or authorization is expired/inactive.")
    if status == "approved" and not 0 < approved_amount <= record.requested_amount:
        raise ValidationError("Approved amount must be positive and within the requested amount.")
    if not reason.strip():
        raise ValidationError("A decision reason is required.")
    record.status, record.reason, record.decided_by = status, reason, actor
    record.approved_amount = approved_amount if status == "approved" else 0
    record.save()
    event(record, actor, "authorization.decided", status=status)
    return record


@transaction.atomic
def assess_claim(record, actor):
    record = m.ClaimAssessment.objects.select_for_update().get(pk=record.pk)
    require_organization(actor, record.organization_id, {"insurance", "insurance_officer"})
    claim = type(record.claim).objects.select_for_update().get(pk=record.claim_id)
    if record.decision != "pending" or claim.status != "submitted":
        raise ValidationError("Claim has already been decided.")
    # A locked coverage row serializes annual-limit consumption across claims.
    coverage = PatientCoverage.objects.select_for_update().filter(patient=claim.patient, policy=claim.policy, active=True).first()
    rule = m.BenefitRule.objects.select_for_update().filter(policy=claim.policy, service_code=record.service_code, active=True).first()
    covered, reason = 0, "No active coverage or matching benefit rule."
    if coverage and rule:
        approved = True
        cap = claim.amount
        if rule.requires_authorization:
            auth = m.Preauthorization.objects.select_for_update().filter(pk=record.authorization_id, coverage=coverage, service_code=record.service_code, status="approved", expires_on__gte=timezone.localdate()).first()
            if not auth:
                approved, reason = False, "A valid preauthorization is required."
            else:
                consumed = m.ClaimAssessment.objects.filter(authorization=auth, decision="approved").aggregate(total=Sum("covered_amount"))["total"] or 0
                cap = max(0, auth.approved_amount - consumed)
        if approved:
            used = m.ClaimAssessment.objects.filter(claim__patient=claim.patient, claim__policy=claim.policy, decision="approved", created_at__year=timezone.localdate().year).aggregate(total=Sum("covered_amount"))["total"] or 0
            covered = min(int(Decimal(claim.amount) * rule.coverage_percent / 100), max(0, rule.annual_limit - used), cap)
            reason = "Benefit rule applied." if covered else "Benefit limit exhausted."
        record.rule_snapshot = {"rule_id": rule.pk, "coverage_percent": rule.coverage_percent, "annual_limit": rule.annual_limit, "requires_authorization": rule.requires_authorization}
    record.covered_amount, record.patient_amount = covered, claim.amount - covered
    record.decision = "approved" if covered else "rejected"
    record.reason = reason
    record.save()
    claim.status = record.decision
    claim.save(update_fields=["status"])
    event(record, actor, "claim.assessed", covered_amount=covered, decision=record.decision)
    return record


@transaction.atomic
def merge_identity(source, target, actor, reason):
    require_role(actor, set())
    locked = {p.pk: p for p in m.Person.objects.select_for_update().filter(pk__in=sorted([source.pk, target.pk])).order_by("pk")}
    source, target = locked[source.pk], locked[target.pk]
    if source.pk == target.pk or source.merged_into_id or target.merged_into_id or not reason.strip():
        raise ValidationError("Two distinct, unmerged identities and a reason are required.")
    if m.Person.objects.filter(merged_into=source).exists():
        raise ValidationError("Reverse earlier merges into the source before merging it.")
    source.merged_into = target
    source.version += 1
    source.save()
    merge = m.IdentityMerge.objects.create(source=source, target=target, actor=actor, reason=reason)
    # Deliberately retain all original foreign keys: a merge must never silently grant clinical access.
    event(source, actor, "identity.merged", target_id=target.pk, merge_id=merge.pk)
    return merge


@transaction.atomic
def unmerge_identity(merge, actor, reason):
    require_role(actor, set())
    merge = m.IdentityMerge.objects.select_for_update().get(pk=merge.pk)
    source = m.Person.objects.select_for_update().get(pk=merge.source_id)
    if merge.reversed_at or source.merged_into_id != merge.target_id or not reason.strip():
        raise ValidationError("Merge is not reversible or a reason is missing.")
    source.merged_into = None
    source.version += 1
    source.save()
    merge.reversed_at, merge.reversed_by, merge.reversal_reason = timezone.now(), actor, reason
    merge.save()
    event(source, actor, "identity.unmerged", merge_id=merge.pk)
    return merge


@transaction.atomic
def imaging_action(record, actor, status, *, version, study_uid="", report="", scheduled_at=None):
    record = m.ImagingOrder.objects.select_for_update().get(pk=record.pk)
    require_organization(actor, record.organization_id, {"doctor", "lab_technician", "facility_manager"})
    expect_version(record, version)
    transitions = {"ordered": {"scheduled", "cancelled"}, "scheduled": {"acquired", "cancelled"}, "acquired": {"reported"}}
    if status not in transitions.get(record.status, set()):
        raise ValidationError("Invalid imaging transition.")
    if status == "scheduled":
        if not scheduled_at or scheduled_at <= timezone.now():
            raise ValidationError("A future appointment time is required.")
        record.scheduled_at = scheduled_at
    if status == "acquired":
        require_role(actor, {"doctor", "lab_technician"})
        import re
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", study_uid) or len(study_uid) > 64:
            raise ValidationError("A valid DICOM study UID is required.")
        record.study_uid = study_uid
    if status == "reported":
        require_role(actor, {"doctor"})
        if not report.strip():
            raise ValidationError("A diagnostic report is required.")
        record.report, record.reported_by, record.reported_at = report, actor, timezone.now()
    record.status = status
    record.version += 1
    record.save()
    event(record, actor, "imaging.transition", status=status, version=record.version)
    return record


def evaluate_medications(names):
    from collections import Counter
    normalized = {name.strip().casefold() for name in names}
    counts = Counter(name.strip().casefold() for name in names)
    rules = m.ClinicalRule.objects.filter(active=True, approved_by__isnull=False)
    alerts = [{"code": rule.code, "version": rule.version, "severity": rule.severity, "message": rule.message, "evidence_url": rule.evidence_url}
              for rule in rules if rule.medicine_a.casefold() in normalized and rule.medicine_b.casefold() in normalized
              and (rule.kind != "duplication" or rule.medicine_a.casefold() != rule.medicine_b.casefold() or counts[rule.medicine_a.casefold()] > 1)]
    return {"alerts": alerts, "knowledge_rules": rules.count(), "complete_safety_check": False}


def offline_cipher():
    from cryptography.fernet import Fernet
    from rest_framework.exceptions import APIException
    key = settings.OFFLINE_ENCRYPTION_KEY
    if not key:
        error = APIException("Offline encryption is not configured.")
        error.status_code = 503
        raise error
    return Fernet(key.encode())


@transaction.atomic
def submit_offline(node, actor, change_id, patient, kind, payload):
    require_organization(actor, node.organization_id, {"doctor", "nurse"})
    if not node.active:
        raise ValidationError("Offline node is inactive.")
    patient_is_valid(patient)
    if not m.Admission.objects.filter(organization=node.organization, patient=patient, status="admitted").exists():
        from workforce.models import PatientVisit
        if not PatientVisit.objects.filter(organization=node.organization, patient=patient).exclude(status__in=["completed", "cancelled"]).exists():
            raise PermissionDenied("Patient is not receiving care at this facility.")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > 32000:
        raise ValidationError("Offline payload is too large.")
    digest = hashlib.sha256(raw).hexdigest()
    # Lock the node to serialize duplicate uploads across workers.
    m.OfflineNode.objects.select_for_update().get(pk=node.pk)
    previous = m.OfflineChange.objects.filter(node=node, change_id=change_id).first()
    if previous:
        if (previous.payload_digest, previous.patient_id, previous.kind) != (digest, patient.pk, kind):
            raise ValidationError("Change ID was reused for different data.")
        return previous
    record = m.OfflineChange.objects.create(node=node, change_id=change_id, patient=patient, kind=kind,
        encrypted_payload=offline_cipher().encrypt(raw), payload_digest=digest)
    event(node, actor, "offline.submitted", change_id=str(change_id))
    return record


@transaction.atomic
def review_offline(record, actor, decision, reason):
    record = m.OfflineChange.objects.select_for_update().select_related("node").get(pk=record.pk)
    require_organization(actor, record.node.organization_id, {"doctor", "nurse"})
    if record.status != "pending" or not reason.strip():
        raise ValidationError("A pending change and review reason are required.")
    if decision == "apply":
        payload = json.loads(offline_cipher().decrypt(bytes(record.encrypted_payload)))
        # Recheck facility assignment at review time as membership and care can change while offline.
        from workforce.models import PatientVisit
        if not m.Admission.objects.filter(organization=record.node.organization, patient=record.patient, status="admitted").exists() and not PatientVisit.objects.filter(organization=record.node.organization, patient=record.patient).exclude(status__in=["completed", "cancelled"]).exists():
            raise PermissionDenied("Patient is no longer receiving care at this facility.")
        if record.kind == "observation":
            from clinical.models import Observation
            from .serializers import OfflineObservationSerializer
            serializer = OfflineObservationSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            obj = Observation(patient=record.patient, recorded_by=actor, source="offline_reviewed", **serializer.validated_data)
        else:
            from workforce.models import NursingNote
            from .serializers import OfflineNoteSerializer
            serializer = OfflineNoteSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            visit = serializer.validated_data.pop("visit")
            if visit.patient_id != record.patient_id or visit.organization_id != record.node.organization_id:
                raise ValidationError("Nursing note visit belongs to a different patient or facility.")
            obj = NursingNote(visit=visit, nurse=actor, **serializer.validated_data)
        obj.full_clean()
        obj.save()
        record.result_id, record.status = obj.pk, "applied"
    elif decision == "reject":
        record.status = "rejected"
    else:
        raise ValidationError("Decision must be apply or reject.")
    record.reviewed_by, record.reason = actor, reason
    record.save()
    event(record.node, actor, "offline.reviewed", change_id=str(record.change_id), status=record.status)
    return record
