from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from operations import models as m, services
from operations.access import require_role
from operations.serializers import StrictSerializer
from operations.views import validated

from .models import Medicine, PharmacyOrder
from .views import require_provider_account


class ReviewInput(StrictSerializer):
    notes = serializers.CharField(max_length=2000)
    counselling = serializers.CharField(max_length=2000)
    product_ids = serializers.DictField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    other_medicines = serializers.ListField(child=serializers.CharField(max_length=250), max_length=100, default=list)


class SubstitutionInput(StrictSerializer):
    item = serializers.IntegerField(min_value=1)
    replacement = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=2000)


class DecisionInput(StrictSerializer):
    decision = serializers.ChoiceField(choices=("approved", "rejected"))
    note = serializers.CharField(max_length=2000)


class SubstitutionSerializer(serializers.ModelSerializer):
    replacement_name = serializers.CharField(source="replacement.name")
    prescribed_medicine = serializers.CharField(source="item.medicine_name")
    prescribed_dose = serializers.CharField(source="item.dosage")
    prescribed_route = serializers.CharField(source="item.route")
    prescribed_frequency = serializers.CharField(source="item.frequency")
    prescribed_duration = serializers.CharField(source="item.duration")
    prescribed_quantity = serializers.IntegerField(source="item.quantity")
    replacement_description = serializers.CharField(source="replacement.description")

    class Meta:
        model = m.PharmacySubstitution
        fields = ("id", "order", "item", "replacement", "replacement_name", "prescribed_medicine",
                  "prescribed_dose", "prescribed_route", "prescribed_frequency", "prescribed_duration",
                  "prescribed_quantity", "replacement_description", "reason", "status", "decision_note", "prescription_version")


def order_for_pharmacist(request, pk, *, lock=False):
    require_role(request.user, {"pharmacist"})
    account, denied = require_provider_account(request, User.Role.PHARMACY)
    if denied is not None:
        raise PermissionDenied("A verified pharmacy affiliation is required.")
    qs = PharmacyOrder.objects.filter(pharmacy=account)
    if lock:
        qs = qs.select_for_update()
    return get_object_or_404(qs, pk=pk)


def valid_prescription(order):
    from prescriptions.models import Prescription
    prescription = Prescription.objects.select_for_update().filter(pk=order.prescription_id).first()
    if (not prescription or prescription.patient_id != order.patient_id or not prescription.signed_at
            or prescription.expires_at <= timezone.now()
            or prescription.status not in {"issued", "partially_dispensed", "dispensed"}
            or order.status != "prepared"):
        raise ValidationError("A prepared order with a valid signed prescription is required.")
    return prescription


class PharmacyPrescriptionReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        order = order_for_pharmacist(request, pk, lock=True)
        prescription = valid_prescription(order)
        data = validated(ReviewInput, request)
        substitutions = dict(order.substitutions.filter(status="approved", prescription_version=prescription.version)
                             .values_list("item_id", "replacement_id"))
        items = list(prescription.items.all())
        selections = data["product_ids"]
        if set(selections) != {str(item.pk) for item in items}:
            raise ValidationError("Verify one pharmacy product for every prescription item.")
        products = Medicine.objects.filter(pharmacy_id=order.pharmacy_id, pk__in=selections.values()).in_bulk()
        for item in items:
            product = products.get(selections[str(item.pk)])
            expected_replacement = substitutions.get(item.pk)
            if (not product or product.sale_type == "unclassified"
                    or (product.pk != expected_replacement if expected_replacement else
                        product.name.strip().casefold() != item.medicine_name.strip().casefold())):
                raise ValidationError("Select a classified product matching each prescribed medicine or approved substitute.")
            if order.dispensing_movements.filter(
                prescription_item=item, kind="dispensed", reversal__isnull=True,
            ).exclude(batch__medicine=product).exists():
                raise ValidationError("A reviewed product cannot change after it has been dispensed.")
        names = [products[selections[str(item.pk)]].name if item.pk in substitutions else
                 item.generic_name or item.medicine_name for item in items]
        check = services.evaluate_medications(names + data.pop("other_medicines"))
        review, _ = m.PharmacyPrescriptionReview.objects.update_or_create(
            order=order, defaults={**data, "reviewer": request.user,
                                   "prescription_version": prescription.version, "medication_check": check},
        )
        services.event(order, request.user, "pharmacy.prescription_reviewed", review_id=review.pk, alerts=len(check["alerts"]))
        return Response({"id": review.pk, "medication_check": check, "counselling": review.counselling})


class PharmacySubstitutionRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        order = order_for_pharmacist(request, pk, lock=True)
        prescription = valid_prescription(order)
        values = validated(SubstitutionInput, request)
        item = get_object_or_404(prescription.items, pk=values["item"])
        replacement = get_object_or_404(Medicine, pk=values["replacement"], pharmacy_id=order.pharmacy_id)
        if (item.dispensed_quantity or replacement.sale_type in {"unclassified", "controlled"}
                or replacement.batches.filter(controlled=True).exists()
                or replacement.name.strip().casefold() == item.medicine_name.strip().casefold()):
            raise ValidationError("A classified, non-controlled replacement is required before any quantity is dispensed.")
        if order.substitutions.filter(item=item, status__in=["pending", "approved"]).exists():
            raise ValidationError("An active request already exists for this prescription item.")
        submission = m.PharmacySubstitution.objects.create(
            order=order, item=item, replacement=replacement, requested_by=request.user,
            reason=values["reason"], prescription_version=prescription.version,
        )
        from communication.services import notify
        notify(prescription.doctor, "Prescription substitution request",
               "Review the requested replacement in your prescription workspace.",
               action_url="/doctor/pharmacy-substitutions", channels=["in_app"])
        services.event(order, request.user, "pharmacy.substitution_requested", substitution_id=submission.pk)
        return Response(SubstitutionSerializer(submission).data, status=201)


class PrescriberSubstitutionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        require_role(request.user, {"doctor"})
        rows = m.PharmacySubstitution.objects.filter(item__prescription__doctor=request.user).select_related("item", "replacement").order_by("-pk")
        if pk is not None:
            return Response(SubstitutionSerializer(get_object_or_404(rows, pk=pk)).data)
        return Response(SubstitutionSerializer(rows, many=True).data)

    @transaction.atomic
    def post(self, request, pk):
        require_role(request.user, {"doctor"})
        available = m.PharmacySubstitution.objects.filter(item__prescription__doctor=request.user)
        request_row = get_object_or_404(available, pk=pk)
        order = PharmacyOrder.objects.select_for_update().get(pk=request_row.order_id)
        prescription = valid_prescription(order)
        row = available.select_for_update().get(pk=pk)
        values = validated(DecisionInput, request)
        if row.status != "pending" or row.prescription_version != prescription.version or row.item.dispensed_quantity:
            raise ValidationError("This request is no longer awaiting a decision for the current prescription.")
        row.status = values["decision"]
        row.decided_by = request.user
        row.decision_note = values["note"]
        row.save(update_fields=["status", "decided_by", "decision_note", "updated_at"])
        if row.status == "approved":
            m.PharmacyPrescriptionReview.objects.filter(order=order).update(prescription_version=0)
        services.event(order, request.user, f"pharmacy.substitution_{row.status}", substitution_id=row.pk)
        return Response(SubstitutionSerializer(row).data)
