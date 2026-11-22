from django.db import transaction
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import PatientProfile
from governance.services import audit

from .models import Order, PharmacyOrder, PharmacyOrderIssue
from .pharmacy_permissions import require_pharmacy_permission
from .pharmacy_sales import staff_pharmacy

SALES = {"failed_delivery", "missed_pickup", "contact_needed", "cancellation_request", "order_help"}
PRESCRIPTION = {"partial_fill", "unavailable", "clarification"}


class AddressInput(serializers.Serializer):
    address = serializers.CharField(max_length=255, allow_blank=True)


class BuyerAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def profile(self, request):
        if request.user.role != "patient":
            raise PermissionDenied("A buyer account is required.")
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        return profile

    def get(self, request):
        if request.user.role != "patient":
            raise PermissionDenied("A buyer account is required.")
        return Response({"address": PatientProfile.objects.filter(user=request.user).values_list("address", flat=True).first() or ""})

    def put(self, request):
        data = AddressInput(data=request.data)
        data.is_valid(raise_exception=True)
        profile = self.profile(request)
        profile.address = data.validated_data["address"]
        profile.save(update_fields=["address"])
        return Response({"address": profile.address})


class IssueInput(serializers.Serializer):
    category = serializers.ChoiceField(choices=sorted(SALES | PRESCRIPTION))
    note = serializers.CharField(max_length=1000)


class ResolveIssue(serializers.Serializer):
    outcome = serializers.CharField(max_length=1000)


class PharmacyIssueView(APIView):
    permission_classes = [IsAuthenticated]

    def get_order(self, request, pk, kind, *, write=False):
        if kind not in {"sales", "rx"}:
            raise ValidationError("Unknown order type.")
        buyer = request.user.role == "patient"
        if buyer:
            if kind != "sales":
                raise PermissionDenied("This queue is restricted to pharmacy staff.")
            return get_object_or_404(Order, pk=pk, patient=request.user)
        pharmacy = staff_pharmacy(request.user)
        page = "rx-orders" if kind == "rx" else "orders"
        action = "rx_manage" if kind == "rx" else "fulfil"
        if write and kind == "rx" and (request.user.role != "pharmacist" or not request.user.is_verified):
            raise PermissionDenied("A verified pharmacist must document prescription exceptions.")
        require_pharmacy_permission(request.user, pharmacy.owner_id, page, *([action] if write else []))
        return get_object_or_404(PharmacyOrder if kind == "rx" else Order, pk=pk, pharmacy=pharmacy.owner)

    def get(self, request, kind, pk, issue=None):
        order = self.get_order(request, pk, kind)
        rows = order.issues.all()
        if request.user.role == "patient":
            rows = rows.filter(opened_by=request.user)
        if issue is not None:
            rows = rows.filter(pk=issue)
        return Response(list(rows.order_by("-pk").values("id", "category", "note", "outcome", "created_at", "resolved_at")[:100]))

    @transaction.atomic
    def post(self, request, kind, pk, issue=None):
        if issue is not None:
            raise ValidationError("Open an issue from the order.")
        order = self.get_order(request, pk, kind, write=True)
        data = IssueInput(data=request.data)
        data.is_valid(raise_exception=True)
        category = data.validated_data["category"]
        if category not in (PRESCRIPTION if kind == "rx" else SALES):
            raise ValidationError("Choose a category for this order type.")
        if request.user.role == "patient" and category not in {"order_help", "cancellation_request"}:
            raise PermissionDenied("Buyers may request help or cancellation.")
        if category == "cancellation_request" and order.status in {"cancelled", "delivered", "dispatched"}:
            raise ValidationError("This order can no longer be cancelled. Request help instead.")
        row = PharmacyOrderIssue.objects.create(
            **({"prescription_order": order} if kind == "rx" else {"order": order}),
            opened_by=request.user, **data.validated_data,
        )
        audit(actor=request.user, action="pharmacy.order_issue.opened", resource=row,
              metadata={"pharmacy_id": order.pharmacy_id}, purpose="operations", request=request)
        if kind == "rx" and category == "clarification":
            from communication.services import notify

            prescription = order.get_prescription()
            if prescription and prescription.patient_id == order.patient_id:
                notify(prescription.doctor, "Prescription clarification requested",
                       "A pharmacy has requested clarification on a prescription.",
                       kind="pharmacy", action_url="/doctor/pharmacy-clarifications", channels=["in_app"])
        return Response({"id": row.pk}, status=201)

    @transaction.atomic
    def patch(self, request, kind, pk, issue=None):
        if issue is None:
            raise ValidationError("Choose an issue to resolve.")
        if request.user.role == "patient":
            raise PermissionDenied("Only pharmacy staff can record the outcome.")
        order = self.get_order(request, pk, kind, write=True)
        row = get_object_or_404(order.issues.select_for_update(), pk=issue)
        if row.resolved_at:
            raise ValidationError("This issue was already resolved.")
        data = ResolveIssue(data=request.data)
        data.is_valid(raise_exception=True)
        row.outcome = data.validated_data["outcome"]
        row.resolved_by = request.user
        row.resolved_at = timezone.now()
        row.save(update_fields=["outcome", "resolved_by", "resolved_at"])
        audit(actor=request.user, action="pharmacy.order_issue.resolved", resource=row,
              metadata={"pharmacy_id": order.pharmacy_id}, purpose="operations", request=request)
        return Response({"id": row.pk})


class PrescriberIssueView(APIView):
    permission_classes = [IsAuthenticated]

    def queryset(self, request):
        from prescriptions.models import Prescription

        if request.user.role != "doctor" or not request.user.is_verified:
            raise PermissionDenied("Only the verified prescriber can review these clarifications.")
        return PharmacyOrderIssue.objects.filter(
            category="clarification",
        ).filter(Exists(Prescription.objects.filter(
            doctor=request.user, pk=OuterRef("prescription_order__prescription_id"),
            patient_id=OuterRef("prescription_order__patient_id"),
        )))

    def get(self, request, pk=None):
        rows = self.queryset(request).order_by("-pk")
        if pk is not None:
            rows = rows.filter(pk=pk)
        return Response(list(rows.values("id", "prescription_order_id", "note", "outcome", "resolved_at")[:100]))

    @transaction.atomic
    def patch(self, request, pk=None):
        if pk is None:
            raise ValidationError("Choose a clarification.")
        row = get_object_or_404(self.queryset(request).select_for_update(of=("self",)), pk=pk)
        if row.resolved_at:
            raise ValidationError("This clarification has already been resolved.")
        data = ResolveIssue(data=request.data)
        data.is_valid(raise_exception=True)
        row.outcome = data.validated_data["outcome"]
        row.resolved_by = request.user
        row.resolved_at = timezone.now()
        row.save(update_fields=["outcome", "resolved_by", "resolved_at"])
        audit(actor=request.user, action="pharmacy.prescription_clarification.answered", resource=row,
              metadata={"pharmacy_id": row.prescription_order.pharmacy_id}, purpose="treatment", request=request)
        return Response({"id": row.pk})
