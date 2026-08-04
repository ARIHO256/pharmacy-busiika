from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from rest_framework import status as drf_status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole, request_role
from accounts.roles import ALLIED_HEALTH_ROLES, CLINICAL_ROLES, DOCTOR_ROLES, NURSING_ROLES
from workforce.access import organization_for_user
from enterprise.access import active_role

from config.uploads import validate_clinical_document_upload

from .models import (
    Bed,
    CartItem,
    HospitalBooking,
    HospitalService,
    InsuranceClaim,
    InsuranceClaimItem,
    InsuranceBenefitRule,
    InsuranceEligibilityCheck,
    InsurancePreauthorization,
    InsuranceRemittance,
    InsurancePolicy,
    CriticalResultAcknowledgement,
    DispensingItem,
    DispensingRecord,
    LabOrder,
    LabTestPanel,
    LabResult,
    LabTest,
    Medicine,
    Order,
    OrderItem,
    PatientCoverage,
    PharmacyOrder,
    Supplier,
    SpecimenEvent,
)
from .serializers import (
    BedSerializer,
    CartItemSerializer,
    HospitalBookingSerializer,
    HospitalServiceSerializer,
    InsuranceClaimSerializer,
    InsuranceBenefitRuleSerializer,
    InsuranceEligibilityCheckSerializer,
    InsurancePreauthorizationSerializer,
    InsuranceRemittanceSerializer,
    InsurancePolicySerializer,
    DispensingRecordSerializer,
    LabOrderSerializer,
    LabTestPanelSerializer,
    LabResultSerializer,
    LabTestSerializer,
    MedicineSerializer,
    OrderSerializer,
    PatientCoverageSerializer,
    PharmacyOrderSerializer,
    ProviderDirectorySerializer,
    SupplierSerializer,
    SpecimenEventSerializer,
)

User = get_user_model()


PROVIDER_STAFF_ROLES = {
    User.Role.FACILITY_MANAGER,
    User.Role.PHARMACIST,
    User.Role.LAB_TECHNICIAN,
    User.Role.RECEPTIONIST,
    User.Role.INSURANCE_OFFICER,
    User.Role.STOREKEEPER,
}


def provider_account_for(user, expected_role):
    """Resolve the organization owner account used by legacy service tables.

    Service models pre-date multi-user organizations and store the owner User as
    the provider foreign key. Staff now operate through organization membership,
    so endpoints translate staff context back to the provider account without
    exposing another organization's data.
    """
    if not user or not user.is_authenticated:
        return None
    role = active_role(user)
    if role in {User.Role.PHARMACIST, User.Role.LAB_TECHNICIAN} and not user.is_verified:
        return None
    if role == expected_role:
        return user
    organization = organization_for_user(user)
    if organization and organization.owner_id and organization.owner.role == expected_role:
        return organization.owner
    return None


def require_provider_account(request, expected_role):
    account = provider_account_for(request.user, expected_role)
    if account is None:
        return None, err("Your account is not assigned to this provider workspace.", drf_status.HTTP_403_FORBIDDEN)
    return account, None


def err(message, code=drf_status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message}, status=code)


def verified_provider_directory(role):
    """Return [{id, org_name, address}] for verified providers of `role`.

    ProviderProfile lives in accounts (built in parallel) — import lazily and
    fall back to is_verified users when the model is unavailable.
    """
    try:
        from accounts.models import ProviderProfile
    except Exception:
        ProviderProfile = None

    rows = []
    if ProviderProfile is not None:
        try:
            profiles = (
                ProviderProfile.objects.filter(status="verified", user__role=role)
                .select_related("user")
            )
            for p in profiles:
                name = p.org_name or f"{p.user.first_name} {p.user.last_name}".strip() or p.user.email
                rows.append({"id": p.user_id, "org_name": name, "address": p.address})
            return rows
        except Exception:
            pass
    for u in User.objects.filter(role=role, is_verified=True):
        name = f"{u.first_name} {u.last_name}".strip() or u.email
        rows.append({"id": u.id, "org_name": name, "address": ""})
    return rows


class ProviderDirectoryView(APIView):
    permission_classes = [AllowAny]
    role = None

    def get(self, request):
        data = verified_provider_directory(self.role)
        return Response(ProviderDirectorySerializer(data, many=True).data)


class PharmacyListView(ProviderDirectoryView):
    role = User.Role.PHARMACY


class LabListView(ProviderDirectoryView):
    role = User.Role.LAB


class HospitalListView(ProviderDirectoryView):
    role = User.Role.HOSPITAL


class InsurerListView(ProviderDirectoryView):
    role = User.Role.INSURANCE


# ---------------------------------------------------------------------------
# PHARMACY — medicines
# ---------------------------------------------------------------------------
class MedicineListCreateView(APIView):
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsRole()]

    def get(self, request):
        qs = Medicine.objects.all().order_by("id")
        pharmacy = request.query_params.get("pharmacy")
        search = request.query_params.get("search")
        if (
            request.user.is_authenticated
            and provider_account_for(request.user, User.Role.PHARMACY) is not None
            and not pharmacy
        ):
            qs = qs.filter(pharmacy=provider_account_for(request.user, User.Role.PHARMACY))
        if pharmacy:
            qs = qs.filter(pharmacy_id=pharmacy)
        if search:
            qs = qs.filter(name__icontains=search)
        ser = MedicineSerializer(qs, many=True, context={"request": request})
        return Response(ser.data)

    def post(self, request):
        ser = MedicineSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return err(str(ser.errors))
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        med = ser.save(pharmacy=pharmacy_account)
        return Response(
            MedicineSerializer(med, context={"request": request}).data,
            status=drf_status.HTTP_201_CREATED,
        )


class MedicineDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]

    def _get_own(self, request, pk):
        med = get_object_or_404(Medicine, pk=pk)
        pharmacy_account = provider_account_for(request.user, User.Role.PHARMACY)
        if pharmacy_account is None or med.pharmacy_id != pharmacy_account.id:
            return None
        return med

    def put(self, request, pk):
        med = self._get_own(request, pk)
        if med is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        ser = MedicineSerializer(med, data=request.data, partial=True, context={"request": request})
        if not ser.is_valid():
            return err(str(ser.errors))
        ser.save()
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        med = self._get_own(request, pk)
        if med is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        med.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# PHARMACY — cart
# ---------------------------------------------------------------------------
class CartListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT]

    def get(self, request):
        qs = CartItem.objects.filter(patient=request.user).select_related("medicine")
        return Response(CartItemSerializer(qs, many=True, context={"request": request}).data)

    def post(self, request):
        medicine_id = request.data.get("medicine_id")
        try:
            qty = int(request.data.get("qty", 1))
        except (TypeError, ValueError):
            return err("qty must be an integer.")
        if qty < 1:
            return err("qty must be at least 1.")
        medicine = Medicine.objects.filter(pk=medicine_id).first()
        if medicine is None:
            return err("Medicine not found.", drf_status.HTTP_404_NOT_FOUND)
        item = CartItem.objects.filter(patient=request.user, medicine=medicine).first()
        if item is not None:
            item.qty += qty
            item.save(update_fields=["qty"])
        else:
            item = CartItem.objects.create(patient=request.user, medicine=medicine, qty=qty)
        return Response(
            CartItemSerializer(item, context={"request": request}).data,
            status=drf_status.HTTP_201_CREATED,
        )


class CartDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT]

    def delete(self, request, pk):
        item = CartItem.objects.filter(pk=pk, patient=request.user).first()
        if item is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# PHARMACY — orders
# ---------------------------------------------------------------------------
class CheckoutView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT]

    def post(self, request):
        delivery = bool(request.data.get("delivery", False))
        address = request.data.get("address", "") or ""
        if delivery and not address:
            return err("address is required when delivery is requested.")
        cart = list(CartItem.objects.filter(patient=request.user).select_related("medicine"))
        if not cart:
            return err("Cart is empty.")

        groups = {}
        for item in cart:
            groups.setdefault(item.medicine.pharmacy_id, []).append(item)

        orders = []
        for pharmacy_id, items in groups.items():
            total = sum(i.medicine.price * i.qty for i in items)
            order = Order.objects.create(
                patient=request.user,
                pharmacy_id=pharmacy_id,
                total=total,
                delivery=delivery,
                address=address,
            )
            for i in items:
                OrderItem.objects.create(
                    order=order,
                    medicine=i.medicine,
                    name=i.medicine.name,
                    price=i.medicine.price,
                    qty=i.qty,
                )
                i.medicine.stock = max(0, i.medicine.stock - i.qty)
                i.medicine.save(update_fields=["stock"])
            orders.append(order)

        CartItem.objects.filter(patient=request.user).delete()
        return Response(
            OrderSerializer(orders, many=True, context={"request": request}).data,
            status=drf_status.HTTP_201_CREATED,
        )


class OrderListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT, User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER]

    def get(self, request):
        if request_role(request) in {User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER}:
            pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
            if denied:
                return denied
            qs = Order.objects.filter(pharmacy=pharmacy_account)
        else:
            qs = Order.objects.filter(patient=request.user)
        qs = qs.prefetch_related("items").order_by("-created_at")
        return Response(OrderSerializer(qs, many=True, context={"request": request}).data)


class OrderUpdateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]
    ALLOWED = {Order.Status.CONFIRMED, Order.Status.DELIVERED, Order.Status.CANCELLED}

    def post(self, request, pk):
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        order = Order.objects.filter(pk=pk, pharmacy=pharmacy_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        new_status = request.data.get("status")
        if new_status not in self.ALLOWED:
            return err("status must be one of confirmed|delivered|cancelled.")
        order.status = new_status
        order.save(update_fields=["status"])
        return Response(OrderSerializer(order, context={"request": request}).data)


# ---------------------------------------------------------------------------
# PHARMACY — prescription orders
# ---------------------------------------------------------------------------
class PharmacyOrderListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]

    def get(self, request):
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        qs = PharmacyOrder.objects.filter(pharmacy=pharmacy_account).order_by("-created_at")
        return Response(PharmacyOrderSerializer(qs, many=True, context={"request": request}).data)


class PharmacyOrderUpdateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST]
    ALLOWED = {
        PharmacyOrder.Status.PREPARED,
        PharmacyOrder.Status.DELIVERED,
        PharmacyOrder.Status.REJECTED,
    }

    def post(self, request, pk):
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        order = PharmacyOrder.objects.filter(pk=pk, pharmacy=pharmacy_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        new_status = request.data.get("status")
        if new_status not in self.ALLOWED:
            return err("status must be one of prepared|delivered|rejected.")
        order.status = new_status
        order.save(update_fields=["status"])
        return Response(PharmacyOrderSerializer(order, context={"request": request}).data)




class DispensingRecordListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER]

    def _order(self, request, pk):
        pharmacy_account = provider_account_for(request.user, User.Role.PHARMACY)
        if pharmacy_account is None:
            return None
        return PharmacyOrder.objects.filter(pk=pk, pharmacy=pharmacy_account).select_related(
            "patient", "pharmacy"
        ).prefetch_related("dispensing_records__items").first()

    def get(self, request, pk):
        order = self._order(request, pk)
        if order is None:
            return err("Prescription order not found.", drf_status.HTTP_404_NOT_FOUND)
        records = order.dispensing_records.select_related("pharmacist").prefetch_related("items")
        return Response(DispensingRecordSerializer(records, many=True).data)

    @transaction.atomic
    def post(self, request, pk):
        if request_role(request) not in {User.Role.PHARMACY, User.Role.PHARMACIST}:
            return err("Only a pharmacy owner or verified pharmacist may dispense.", drf_status.HTTP_403_FORBIDDEN)
        order = self._order(request, pk)
        if order is None:
            return err("Prescription order not found.", drf_status.HTTP_404_NOT_FOUND)
        serializer = DispensingRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data.pop("items", [])
        status_value = serializer.validated_data.get("status", DispensingRecord.Status.REVIEWED)

        # Prevent duplicate over-dispensing across completed or partial records.
        historical = {}
        for row in DispensingItem.objects.filter(
            record__pharmacy_order=order,
            record__status__in=[DispensingRecord.Status.PARTIAL, DispensingRecord.Status.DISPENSED],
        ):
            key = row.prescription_item_id or row.medicine_name.lower()
            historical[key] = historical.get(key, 0) + row.dispensed_quantity
        for item in items:
            prescribed = item.get("prescribed_quantity", 0)
            dispensed = item.get("dispensed_quantity", 0)
            key = item.get("prescription_item_id") or item.get("medicine_name", "").lower()
            if prescribed and historical.get(key, 0) + dispensed > prescribed:
                return err(f"Dispensed quantity exceeds the prescription for {item.get('medicine_name')}.")
            if dispensed:
                medicine = Medicine.objects.select_for_update().filter(
                    pharmacy=order.pharmacy, name__iexact=item.get("medicine_name", "")
                ).first()
                if medicine:
                    if medicine.stock < dispensed:
                        return err(f"Insufficient stock for {medicine.name}.")
                    medicine.stock -= dispensed
                    medicine.save(update_fields=["stock"])

        record = DispensingRecord.objects.create(
            pharmacy_order=order,
            pharmacist=request.user,
            dispensed_at=timezone.now() if status_value in {DispensingRecord.Status.PARTIAL, DispensingRecord.Status.DISPENSED} else None,
            **serializer.validated_data,
        )
        DispensingItem.objects.bulk_create([DispensingItem(record=record, **item) for item in items])
        prescription = order.get_prescription()
        if prescription is not None:
            for item in items:
                item_id = item.get("prescription_item_id")
                if not item_id:
                    continue
                rx_item = prescription.items.select_for_update().filter(pk=item_id).first()
                if rx_item is None:
                    continue
                key = item_id
                rx_item.dispensed_quantity = min(
                    rx_item.quantity, historical.get(key, 0) + item.get("dispensed_quantity", 0)
                )
                rx_item.save(update_fields=["dispensed_quantity"])
            try:
                from prescriptions.models import Prescription
                remaining = any(row.dispensed_quantity < row.quantity for row in prescription.items.all())
                prescription.status = (
                    Prescription.Status.PARTIALLY_DISPENSED if remaining
                    else Prescription.Status.DISPENSED
                )
                if status_value in {DispensingRecord.Status.CANCELLED, DispensingRecord.Status.HELD, DispensingRecord.Status.CLARIFICATION}:
                    prescription.status = Prescription.Status.ISSUED
                prescription.save(update_fields=["status"])
            except Exception:
                pass
        if status_value == DispensingRecord.Status.DISPENSED:
            order.status = PharmacyOrder.Status.DELIVERED
        elif status_value == DispensingRecord.Status.PARTIAL:
            order.status = PharmacyOrder.Status.PREPARED
        elif status_value == DispensingRecord.Status.CANCELLED:
            order.status = PharmacyOrder.Status.REJECTED
        elif status_value == DispensingRecord.Status.REVIEWED:
            order.status = PharmacyOrder.Status.PREPARED
        order.save(update_fields=["status"])
        try:
            from communication.services import notify
            notify(
                order.patient,
                "Prescription dispensing update",
                f"Your prescription is now {record.get_status_display().lower()}.",
                kind="pharmacy",
                action_url="/patient/prescriptions",
            )
        except Exception:
            pass
        try:
            from governance.services import audit
            from interoperability.services import emit_event
            audit(
                actor=request.user, patient=order.patient, action="pharmacy.dispensing.recorded",
                resource=record, purpose="treatment", request=request,
                metadata={"status": status_value, "item_count": len(items)},
            )
            emit_event(
                "pharmacy.dispensing.recorded", record,
                {"pharmacy_order_id": order.id, "status": status_value, "patient_id": order.patient_id},
                actor=request.user, patient=order.patient, request=request,
            )
        except Exception:
            pass
        record = DispensingRecord.objects.select_related("pharmacist").prefetch_related("items").get(pk=record.pk)
        return Response(DispensingRecordSerializer(record).data, status=drf_status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# PHARMACY — suppliers
# ---------------------------------------------------------------------------
class SupplierListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]

    def get(self, request):
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        qs = Supplier.objects.filter(pharmacy=pharmacy_account).prefetch_related("products")
        return Response(SupplierSerializer(qs, many=True).data)

    def post(self, request):
        ser = SupplierSerializer(data=request.data)
        if not ser.is_valid():
            return err(str(ser.errors))
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        supplier = ser.save(pharmacy=pharmacy_account)
        return Response(SupplierSerializer(supplier).data, status=drf_status.HTTP_201_CREATED)


class SupplierDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]

    def _get_own(self, request, pk):
        pharmacy_account = provider_account_for(request.user, User.Role.PHARMACY)
        if pharmacy_account is None:
            return None
        return Supplier.objects.filter(pk=pk, pharmacy=pharmacy_account).first()

    def put(self, request, pk):
        supplier = self._get_own(request, pk)
        if supplier is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        ser = SupplierSerializer(supplier, data=request.data, partial=True)
        if not ser.is_valid():
            return err(str(ser.errors))
        ser.save()
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        supplier = self._get_own(request, pk)
        if supplier is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        supplier.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# LAB
# ---------------------------------------------------------------------------


class LabTestPanelListCreateView(APIView):
    allowed_roles = [User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsRole()]

    def get(self, request):
        qs = LabTestPanel.objects.filter(active=True).select_related("lab").prefetch_related("items__test")
        lab_id = request.query_params.get("lab")
        if lab_id:
            qs = qs.filter(lab_id=lab_id)
        elif request.user.is_authenticated:
            account = provider_account_for(request.user, User.Role.LAB)
            if account is not None:
                qs = LabTestPanel.objects.filter(lab=account).select_related("lab").prefetch_related("items__test")
        return Response(LabTestPanelSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        lab_account, denied = require_provider_account(request, User.Role.LAB)
        if denied:
            return denied
        serializer = LabTestPanelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tests = [item["test"] for item in serializer.validated_data.get("items", [])]
        if any(test.lab_id != lab_account.id for test in tests):
            return err("Every panel test must belong to this laboratory.")
        panel = serializer.save(lab=lab_account)
        return Response(LabTestPanelSerializer(panel).data, status=drf_status.HTTP_201_CREATED)


class LabTestPanelDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER]

    def _get(self, request, pk):
        account = provider_account_for(request.user, User.Role.LAB)
        return LabTestPanel.objects.filter(pk=pk, lab=account).prefetch_related("items__test").first() if account else None

    @transaction.atomic
    def put(self, request, pk):
        panel = self._get(request, pk)
        if panel is None:
            return err("Panel not found.", drf_status.HTTP_404_NOT_FOUND)
        serializer = LabTestPanelSerializer(panel, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tests = [item["test"] for item in serializer.validated_data.get("items", [])]
        if any(test.lab_id != panel.lab_id for test in tests):
            return err("Every panel test must belong to this laboratory.")
        panel = serializer.save()
        return Response(LabTestPanelSerializer(panel).data)

    patch = put

    def delete(self, request, pk):
        panel = self._get(request, pk)
        if panel is None:
            return err("Panel not found.", drf_status.HTTP_404_NOT_FOUND)
        panel.active = False
        panel.save(update_fields=["active", "updated_at"])
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class LabTestPanelOrderView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list({User.Role.PATIENT} | CLINICAL_ROLES)

    @transaction.atomic
    def post(self, request, pk):
        panel = LabTestPanel.objects.filter(pk=pk, active=True, lab__is_verified=True).select_related("lab").prefetch_related("items__test").first()
        if panel is None:
            return err("Active laboratory panel not found.", drf_status.HTTP_404_NOT_FOUND)
        if request_role(request) == User.Role.PATIENT:
            patient = request.user
            referring_doctor = None
        else:
            patient = User.objects.filter(pk=request.data.get("patient_id") or request.data.get("patient"), role=User.Role.PATIENT).first()
            if patient is None:
                return err("A patient is required.")
            referring_doctor = request.user
        common = {
            "patient": patient,
            "lab": panel.lab,
            "referring_doctor": referring_doctor,
            "referring_facility": str(request.data.get("referring_facility", "")).strip(),
            "clinical_indication": str(request.data.get("clinical_indication", "")).strip(),
            "provisional_diagnosis": str(request.data.get("provisional_diagnosis", "")).strip(),
            "priority": request.data.get("priority") or LabOrder.Priority.ROUTINE,
        }
        orders = [LabOrder.objects.create(test=item.test, specimen_type=item.test.sample_type, **common) for item in panel.items.all()]
        try:
            from communication.services import notify
            notify(
                patient, "Laboratory panel ordered",
                f"{panel.name} ({len(orders)} tests) has been ordered at {panel.lab.display_name}.",
                kind="laboratory", action_url="/patient/health-record",
            )
        except Exception:
            pass
        return Response(LabOrderSerializer(orders, many=True, context={"request": request}).data, status=drf_status.HTTP_201_CREATED)


class SpecimenEventListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [
        User.Role.PATIENT, User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER,
        User.Role.DOCTOR, User.Role.CLINICAL_OFFICER, User.Role.MEDICAL_DIRECTOR, User.Role.ADMIN,
    ]

    def _order(self, request, pk):
        order = LabOrder.objects.filter(pk=pk).select_related("patient", "lab", "referring_doctor").first()
        if order is None:
            return None
        allowed = (
            request_role(request) == User.Role.ADMIN
            or request.user == order.patient
            or request.user == order.referring_doctor
            or provider_account_for(request.user, User.Role.LAB) == order.lab
        )
        return order if allowed else None

    def get(self, request, pk):
        order = self._order(request, pk)
        if order is None:
            return err("Specimen record not found or unavailable.", drf_status.HTTP_404_NOT_FOUND)
        return Response(SpecimenEventSerializer(order.specimen_events.select_related("performed_by"), many=True).data)

    @transaction.atomic
    def post(self, request, pk):
        if request_role(request) not in {User.Role.LAB, User.Role.LAB_TECHNICIAN}:
            return err("Only laboratory staff can update specimen custody.", drf_status.HTTP_403_FORBIDDEN)
        order = self._order(request, pk)
        if order is None:
            return err("Specimen record not found.", drf_status.HTTP_404_NOT_FOUND)
        serializer = SpecimenEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        barcode = serializer.validated_data.get("barcode") or order.specimen_id or f"LAB-{order.id:08d}"
        event = serializer.save(order=order, performed_by=request.user, barcode=barcode)
        fields = []
        if not order.specimen_id:
            order.specimen_id = barcode
            fields.append("specimen_id")
        mapping = {
            SpecimenEvent.Type.COLLECTED: LabOrder.Status.SAMPLE_COLLECTED,
            SpecimenEvent.Type.RECEIVED: LabOrder.Status.SAMPLE_RECEIVED,
            SpecimenEvent.Type.PROCESSING: LabOrder.Status.PROCESSING,
            SpecimenEvent.Type.REJECTED: LabOrder.Status.REJECTED,
        }
        if event.event_type in mapping:
            order.status = mapping[event.event_type]
            fields.append("status")
        if event.event_type == SpecimenEvent.Type.COLLECTED:
            order.collected_by = request.user
            order.collected_at = event.occurred_at
            fields.extend(["collected_by", "collected_at"])
        elif event.event_type == SpecimenEvent.Type.RECEIVED:
            order.received_at = event.occurred_at
            fields.append("received_at")
        elif event.event_type == SpecimenEvent.Type.REJECTED:
            order.rejection_reason = event.notes
            fields.append("rejection_reason")
        if fields:
            order.save(update_fields=list(dict.fromkeys(fields + ["updated_at"])))
        try:
            from governance.services import audit
            from interoperability.services import emit_event
            audit(actor=request.user, patient=order.patient, action=f"laboratory.specimen.{event.event_type}", resource=event, purpose="treatment", request=request)
            emit_event(f"laboratory.specimen.{event.event_type}", event, {"lab_order_id": order.id, "barcode": barcode}, actor=request.user, patient=order.patient, request=request)
        except Exception:
            pass
        return Response(SpecimenEventSerializer(event).data, status=drf_status.HTTP_201_CREATED)


class LabTestListCreateView(APIView):
    allowed_roles = [User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsRole()]

    def get(self, request):
        qs = LabTest.objects.all().order_by("id")
        lab = request.query_params.get("lab")
        search = request.query_params.get("search")
        if (
            request.user.is_authenticated
            and provider_account_for(request.user, User.Role.LAB) is not None
            and not lab
        ):
            qs = qs.filter(lab=provider_account_for(request.user, User.Role.LAB))
        if lab:
            qs = qs.filter(lab_id=lab)
        if search:
            qs = qs.filter(name__icontains=search)
        return Response(LabTestSerializer(qs, many=True).data)

    def post(self, request):
        ser = LabTestSerializer(data=request.data)
        if not ser.is_valid():
            return err(str(ser.errors))
        lab_account, denied = require_provider_account(request, User.Role.LAB)
        if denied:
            return denied
        test = ser.save(lab=lab_account)
        return Response(LabTestSerializer(test).data, status=drf_status.HTTP_201_CREATED)


class LabTestDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER]

    def _get_own(self, request, pk):
        lab_account = provider_account_for(request.user, User.Role.LAB)
        if lab_account is None:
            return None
        return LabTest.objects.filter(pk=pk, lab=lab_account).first()

    def put(self, request, pk):
        test = self._get_own(request, pk)
        if test is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        ser = LabTestSerializer(test, data=request.data, partial=True)
        if not ser.is_valid():
            return err(str(ser.errors))
        ser.save()
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        test = self._get_own(request, pk)
        if test is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        test.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class LabOrderListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list({User.Role.PATIENT} | CLINICAL_ROLES)

    def get(self, request):
        if request_role(request) == User.Role.PATIENT:
            qs = LabOrder.objects.filter(patient=request.user)
        else:
            qs = LabOrder.objects.filter(referring_doctor=request.user)
        qs = qs.select_related("test", "lab", "patient", "referring_doctor").order_by("-created_at")
        return Response(LabOrderSerializer(qs, many=True, context={"request": request}).data)

    def post(self, request):
        lab_id = request.data.get("lab_id") or request.data.get("lab")
        test_id = request.data.get("test_id") or request.data.get("test")
        lab = User.objects.filter(pk=lab_id, role=User.Role.LAB, is_verified=True).first()
        if lab is None:
            return err("A verified laboratory is required.", drf_status.HTTP_404_NOT_FOUND)
        test = LabTest.objects.filter(pk=test_id, lab=lab).first()
        if test is None:
            return err("Test not found for the selected laboratory.", drf_status.HTTP_404_NOT_FOUND)
        if request_role(request) == User.Role.PATIENT:
            patient = request.user
            referring_doctor = None
        else:
            patient_id = request.data.get("patient_id") or request.data.get("patient")
            patient = User.objects.filter(pk=patient_id, role=User.Role.PATIENT).first()
            if patient is None:
                return err("patient_id is required for a clinical referral.")
            referring_doctor = request.user
        order = LabOrder.objects.create(
            patient=patient,
            lab=lab,
            test=test,
            referring_doctor=referring_doctor,
            referring_facility=str(request.data.get("referring_facility", "")).strip(),
            clinical_indication=str(request.data.get("clinical_indication", "")).strip(),
            provisional_diagnosis=str(request.data.get("provisional_diagnosis", "")).strip(),
            priority=request.data.get("priority") or LabOrder.Priority.ROUTINE,
            specimen_type=str(request.data.get("specimen_type", "")).strip() or test.sample_type,
            prescription_id=request.data.get("prescription_id") or None,
        )
        try:
            from communication.services import notify
            notify(
                patient,
                "Laboratory test ordered",
                f"{test.name} has been ordered at {lab.display_name}.",
                kind="laboratory",
                action_url="/patient/health-record",
            )
        except Exception:
            pass
        return Response(
            LabOrderSerializer(order, context={"request": request}).data,
            status=drf_status.HTTP_201_CREATED,
        )

class LabOrderManageView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER]

    def get(self, request):
        lab_account, denied = require_provider_account(request, User.Role.LAB)
        if denied:
            return denied
        qs = LabOrder.objects.filter(lab=lab_account).select_related("test", "patient", "referring_doctor").order_by("-created_at")
        return Response(LabOrderSerializer(qs, many=True, context={"request": request}).data)


class LabOrderUpdateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER]

    def post(self, request, pk):
        lab_account, denied = require_provider_account(request, User.Role.LAB)
        if denied:
            return denied
        order = LabOrder.objects.filter(pk=pk, lab=lab_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        changed = []
        new_status = request.data.get("status")
        if new_status:
            valid = {c for c, _ in LabOrder.Status.choices}
            if new_status not in valid:
                return err("Invalid status.")
            order.status = new_status
            changed.append("status")
            if new_status == LabOrder.Status.SAMPLE_COLLECTED:
                order.collected_by = request.user
                order.collected_at = timezone.now()
                changed.extend(["collected_by", "collected_at"])
            elif new_status == LabOrder.Status.SAMPLE_RECEIVED:
                order.received_at = timezone.now()
                changed.append("received_at")
            elif new_status == LabOrder.Status.COMPLETED:
                order.result_released = True
                order.released_at = timezone.now()
                changed.extend(["result_released", "released_at"])
        editable = [
            "specimen_id", "specimen_type", "collection_notes", "rejection_reason",
            "result_notes", "clinical_indication", "provisional_diagnosis", "priority",
        ]
        for field in editable:
            if field in request.data:
                setattr(order, field, request.data.get(field) or "")
                changed.append(field)
        if "result_file" in request.FILES:
            result_file = request.FILES["result_file"]
            validate_clinical_document_upload(result_file)
            order.result_file = result_file
            changed.append("result_file")
        if changed:
            order.save(update_fields=list(dict.fromkeys(changed + ["updated_at"])))
        if order.result_released:
            try:
                from communication.services import notify
                notify(
                    order.patient,
                    "Laboratory result released",
                    f"Your {order.test.name} result is now available.",
                    kind="laboratory",
                    action_url="/patient/health-record",
                    priority="high" if order.results.filter(interpretation="critical").exists() else "normal",
                )
            except Exception:
                pass
        return Response(LabOrderSerializer(order, context={"request": request}).data)

class LabResultListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list({User.Role.PATIENT, User.Role.LAB, User.Role.ADMIN} | CLINICAL_ROLES)

    def _order_for_user(self, request, pk):
        order = LabOrder.objects.filter(pk=pk).select_related(
            "patient", "lab", "test", "referring_doctor"
        ).first()
        if order is None:
            return None, err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        allowed = (
            request_role(request) == User.Role.ADMIN
            or request.user == order.patient
            or provider_account_for(request.user, User.Role.LAB) == order.lab
            or request.user == order.referring_doctor
        )
        if request_role(request) in (DOCTOR_ROLES | ALLIED_HEALTH_ROLES | {User.Role.ANAESTHETIST, User.Role.PARAMEDIC}) and not allowed:
            from appointments.models import Appointment

            allowed = Appointment.objects.filter(
                doctor=request.user,
                patient=order.patient,
            ).exclude(status="cancelled").exists()
        elif request_role(request) in NURSING_ROLES and not allowed:
            from workforce.models import PatientVisit

            allowed = PatientVisit.objects.filter(
                patient=order.patient,
                assigned_nurse=request.user,
            ).exclude(
                status__in=[PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED]
            ).exists()
        if not allowed:
            return None, err("Not allowed.", drf_status.HTTP_403_FORBIDDEN)
        return order, None

    def get(self, request, pk):
        order, denied = self._order_for_user(request, pk)
        if denied:
            return denied
        qs = order.results.all()
        if request_role(request) == User.Role.PATIENT:
            if not order.result_released:
                return Response([])
            qs = qs.filter(status__in=[LabResult.Status.FINAL, LabResult.Status.AMENDED, LabResult.Status.CORRECTED])
        return Response(LabResultSerializer(qs, many=True).data)

    def post(self, request, pk):
        if request_role(request) not in {User.Role.LAB, User.Role.LAB_TECHNICIAN}:
            return err("Only authorized laboratory staff can enter results.", drf_status.HTTP_403_FORBIDDEN)
        lab_account, denied = require_provider_account(request, User.Role.LAB)
        if denied:
            return denied
        order = LabOrder.objects.filter(pk=pk, lab=lab_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        serializer = LabResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_status = serializer.validated_data.get("status", LabResult.Status.PRELIMINARY)
        release = bool(request.data.get("release", False)) or requested_status in {
            LabResult.Status.FINAL, LabResult.Status.AMENDED, LabResult.Status.CORRECTED
        }
        now = timezone.now()
        result = serializer.save(
            order=order,
            entered_by=request.user,
            verified_by=request.user if release else None,
            verified_at=now if release else None,
            released_by=request.user if release else None,
            released_at=now if release else None,
        )
        if release:
            order.status = LabOrder.Status.COMPLETED
            order.result_released = True
            order.released_at = now
            order.save(update_fields=["status", "result_released", "released_at", "updated_at"])
        else:
            order.status = LabOrder.Status.AWAITING_VALIDATION
            order.save(update_fields=["status", "updated_at"])
        try:
            from communication.services import notify
            body = "A laboratory result is ready. Please open MyDoctor to review it securely."
            if result.interpretation == LabResult.Interpretation.CRITICAL:
                body = "A critical laboratory result requires prompt clinical review. Contact your care team."
            if release:
                notify(
                    order.patient,
                    "Laboratory result available",
                    body,
                    kind="laboratory",
                    priority="urgent" if result.interpretation == LabResult.Interpretation.CRITICAL else "normal",
                    action_url="/patient/health-record",
                )
                if order.referring_doctor:
                    notify(
                        order.referring_doctor,
                        "Referred laboratory result available",
                        f"{order.test.name} results for {order.patient.display_name} are ready.",
                        kind="laboratory",
                        priority="urgent" if result.interpretation == LabResult.Interpretation.CRITICAL else "normal",
                        action_url="/doctor/clinical",
                    )
        except Exception:
            pass
        try:
            from governance.services import audit
            audit(
                actor=request.user, patient=order.patient, action="laboratory.result.entered",
                resource=result, purpose="treatment",
                metadata={"interpretation": result.interpretation, "released": release}, request=request,
            )
        except Exception:
            pass
        try:
            from interoperability.services import emit_event
            emit_event(
                "laboratory.result.released" if release else "laboratory.result.entered",
                result,
                {
                    "lab_order_id": order.id,
                    "patient_id": order.patient_id,
                    "test_id": order.test_id,
                    "status": result.status,
                    "interpretation": result.interpretation,
                    "critical": result.interpretation == LabResult.Interpretation.CRITICAL,
                },
                actor=request.user,
                patient=order.patient,
                request=request,
            )
        except Exception:
            pass
        return Response(LabResultSerializer(result).data, status=drf_status.HTTP_201_CREATED)

class CriticalResultAcknowledgeView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list(DOCTOR_ROLES | NURSING_ROLES | {User.Role.ANAESTHETIST, User.Role.PARAMEDIC, User.Role.ADMIN})

    def post(self, request, pk):
        result = LabResult.objects.filter(pk=pk, interpretation=LabResult.Interpretation.CRITICAL).select_related("order__patient").first()
        if result is None:
            return err("Critical result not found.", drf_status.HTTP_404_NOT_FOUND)
        if request_role(request) in (DOCTOR_ROLES | {User.Role.ANAESTHETIST, User.Role.PARAMEDIC}):
            from appointments.models import Appointment
            if not Appointment.objects.filter(doctor=request.user, patient=result.order.patient).exists():
                return err("No care relationship.", drf_status.HTTP_403_FORBIDDEN)
        ack, created = CriticalResultAcknowledgement.objects.get_or_create(
            result=result,
            defaults={"acknowledged_by": request.user, "notes": request.data.get("notes", "")},
        )
        if created:
            try:
                from governance.services import audit
                from interoperability.services import emit_event

                audit(
                    actor=request.user, patient=result.order.patient,
                    action="laboratory.critical_result.acknowledged", resource=ack,
                    purpose="treatment", request=request,
                )
                emit_event(
                    "laboratory.critical_result.acknowledged",
                    result,
                    {"lab_order_id": result.order_id, "acknowledged_by": request.user.id},
                    actor=request.user, patient=result.order.patient, request=request,
                )
            except Exception:
                pass
        return Response({"acknowledged": True, "created": created, "acknowledged_at": ack.acknowledged_at})


# ---------------------------------------------------------------------------
# HOSPITAL
# ---------------------------------------------------------------------------
class HospitalServiceListCreateView(APIView):
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsRole()]

    def get(self, request):
        qs = HospitalService.objects.all().order_by("id")
        hospital = request.query_params.get("hospital")
        search = request.query_params.get("search")
        if (
            request.user.is_authenticated
            and provider_account_for(request.user, User.Role.HOSPITAL) is not None
            and not hospital
        ):
            qs = qs.filter(hospital=provider_account_for(request.user, User.Role.HOSPITAL))
        if hospital:
            qs = qs.filter(hospital_id=hospital)
        if search:
            qs = qs.filter(name__icontains=search)
        return Response(HospitalServiceSerializer(qs, many=True).data)

    def post(self, request):
        ser = HospitalServiceSerializer(data=request.data)
        if not ser.is_valid():
            return err(str(ser.errors))
        hospital_account, denied = require_provider_account(request, User.Role.HOSPITAL)
        if denied:
            return denied
        service = ser.save(hospital=hospital_account)
        return Response(HospitalServiceSerializer(service).data, status=drf_status.HTTP_201_CREATED)


class HospitalServiceDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    def _get_own(self, request, pk):
        hospital_account = provider_account_for(request.user, User.Role.HOSPITAL)
        if hospital_account is None:
            return None
        return HospitalService.objects.filter(pk=pk, hospital=hospital_account).first()

    def put(self, request, pk):
        service = self._get_own(request, pk)
        if service is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        ser = HospitalServiceSerializer(service, data=request.data, partial=True)
        if not ser.is_valid():
            return err(str(ser.errors))
        ser.save()
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        service = self._get_own(request, pk)
        if service is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        service.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class HospitalBookingListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT]

    def get(self, request):
        qs = (
            HospitalBooking.objects.filter(patient=request.user)
            .select_related("hospital", "service")
            .order_by("-created_at")
        )
        return Response(HospitalBookingSerializer(qs, many=True).data)

    def post(self, request):
        hospital_id = request.data.get("hospital_id")
        service_id = request.data.get("service_id")
        date = request.data.get("date")
        if not date:
            return err("date is required.")
        hospital = User.objects.filter(pk=hospital_id, role=User.Role.HOSPITAL).first()
        if hospital is None:
            return err("Hospital not found.", drf_status.HTTP_404_NOT_FOUND)
        service = None
        if service_id:
            service = HospitalService.objects.filter(pk=service_id, hospital=hospital).first()
            if service is None:
                return err("Service not found.", drf_status.HTTP_404_NOT_FOUND)
        booking = HospitalBooking.objects.create(
            patient=request.user, hospital=hospital, service=service, date=date
        )
        return Response(
            HospitalBookingSerializer(booking).data, status=drf_status.HTTP_201_CREATED
        )


class HospitalBookingManageView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    def get(self, request):
        qs = (
            HospitalBooking.objects.filter(hospital=provider_account_for(request.user, User.Role.HOSPITAL))
            .select_related("patient", "service")
            .order_by("-created_at")
        )
        return Response(HospitalBookingSerializer(qs, many=True).data)


class HospitalBookingUpdateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    def post(self, request, pk):
        hospital_account, denied = require_provider_account(request, User.Role.HOSPITAL)
        if denied:
            return denied
        booking = HospitalBooking.objects.filter(pk=pk, hospital=hospital_account).first()
        if booking is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        new_status = request.data.get("status")
        valid = {c for c, _ in HospitalBooking.Status.choices}
        if new_status not in valid:
            return err("status must be one of pending|confirmed|completed|cancelled.")
        booking.status = new_status
        booking.save(update_fields=["status"])
        return Response(HospitalBookingSerializer(booking).data)


class BedListCreateView(APIView):
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsRole()]

    def get(self, request):
        hospital = request.query_params.get("hospital")
        if hospital:
            qs = Bed.objects.filter(hospital_id=hospital)
        elif request.user.is_authenticated and provider_account_for(request.user, User.Role.HOSPITAL) is not None:
            qs = Bed.objects.filter(hospital=provider_account_for(request.user, User.Role.HOSPITAL))
        else:
            return err("hospital query parameter is required.")
        return Response(BedSerializer(qs.order_by("ward", "label"), many=True).data)

    def post(self, request):
        ser = BedSerializer(data=request.data)
        if not ser.is_valid():
            return err(str(ser.errors))
        hospital_account, denied = require_provider_account(request, User.Role.HOSPITAL)
        if denied:
            return denied
        bed = ser.save(hospital=hospital_account)
        return Response(BedSerializer(bed).data, status=drf_status.HTTP_201_CREATED)


class BedDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    def _get_own(self, request, pk):
        hospital_account = provider_account_for(request.user, User.Role.HOSPITAL)
        if hospital_account is None:
            return None
        return Bed.objects.filter(pk=pk, hospital=hospital_account).first()

    def put(self, request, pk):
        bed = self._get_own(request, pk)
        if bed is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        ser = BedSerializer(bed, data=request.data, partial=True)
        if not ser.is_valid():
            return err(str(ser.errors))
        ser.save()
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        bed = self._get_own(request, pk)
        if bed is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        bed.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class BedToggleView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    def post(self, request, pk):
        hospital_account, denied = require_provider_account(request, User.Role.HOSPITAL)
        if denied:
            return denied
        bed = Bed.objects.filter(pk=pk, hospital=hospital_account).first()
        if bed is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        bed.is_occupied = not bed.is_occupied
        bed.save(update_fields=["is_occupied"])
        return Response(BedSerializer(bed).data)


# ---------------------------------------------------------------------------
# INSURANCE
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# INSURANCE
# ---------------------------------------------------------------------------
INSURANCE_REVIEW_ROLES = [
    User.Role.INSURANCE,
    User.Role.INSURANCE_OFFICER,
    User.Role.CLAIMS_REVIEWER,
    User.Role.FACILITY_MANAGER,
    User.Role.ADMIN,
]
INSURANCE_REQUEST_ROLES = [
    User.Role.PATIENT,
    User.Role.RECEPTIONIST,
    User.Role.CASHIER,
    User.Role.FACILITY_MANAGER,
    User.Role.HOSPITAL,
    User.Role.DOCTOR,
    User.Role.CLINICAL_OFFICER,
    User.Role.MEDICAL_DIRECTOR,
    User.Role.INSURANCE,
    User.Role.INSURANCE_OFFICER,
    User.Role.CLAIMS_REVIEWER,
    User.Role.ADMIN,
]


def _insurance_account(request):
    if request_role(request) == User.Role.ADMIN:
        provider_id = request.query_params.get("provider") or request.data.get("provider_id")
        return User.objects.filter(pk=provider_id, role=User.Role.INSURANCE).first()
    return provider_account_for(request.user, User.Role.INSURANCE)


def _notify_insurance(user, title, body, *, action_url="/patient/insurance", metadata=None):
    try:
        from communication.services import notify

        notify(
            user,
            title,
            body,
            kind="insurance",
            priority="high",
            action_url=action_url,
            channels=["in_app", "email"],
            metadata=metadata or {},
        )
    except Exception:
        pass


def _audit_insurance(request, action, resource, patient=None, metadata=None):
    try:
        from governance.services import audit

        audit(
            actor=request.user,
            patient=patient,
            action=action,
            resource=resource,
            purpose="payment" if "claim" in action or "remittance" in action else "operations",
            metadata=metadata or {},
            request=request,
        )
    except Exception:
        pass


def _policy_rule(policy, service_code="", service_category=""):
    rules = policy.benefit_rules.filter(active=True)
    if service_code:
        exact = rules.filter(service_code__iexact=service_code).first()
        if exact:
            return exact
    if service_category:
        category = rules.filter(service_category__iexact=service_category).first()
        if category:
            return category
    return None


def _evaluate_coverage(coverage, *, service_code="", service_category="", estimated_amount=0):
    """Apply policy and benefit limits to an eligibility request.

    The calculation is deterministic and its complete snapshot is persisted on
    every eligibility check. Contract-specific adjudication can therefore be
    layered on later without losing the decision used at the point of care.
    """
    today = timezone.localdate()
    policy = coverage.policy
    amount = max(int(estimated_amount or 0), 0)
    rule = _policy_rule(policy, service_code, service_category)
    if not coverage.active or not policy.active:
        return {"result": InsuranceEligibilityCheck.Result.INACTIVE, "reason": "Coverage or policy is inactive."}
    if coverage.expires_on and coverage.expires_on < today:
        return {"result": InsuranceEligibilityCheck.Result.EXPIRED, "reason": "Coverage has expired."}
    waiting_days = max(policy.waiting_period_days, getattr(rule, "waiting_period_days", 0) or 0)
    waiting_until = coverage.effective_from + timedelta(days=waiting_days)
    if today < waiting_until:
        return {
            "result": InsuranceEligibilityCheck.Result.WAITING_PERIOD,
            "reason": f"Waiting period ends on {waiting_until}.",
            "waiting_until": str(waiting_until),
        }
    if rule and rule.excluded:
        return {"result": InsuranceEligibilityCheck.Result.INACTIVE, "reason": "The requested service is excluded by this policy."}

    percent = rule.coverage_percent if rule and rule.coverage_percent is not None else policy.coverage_percent
    percent = min(max(int(percent or 0), 0), 100)
    deductible = int(policy.deductible or 0)
    eligible_base = max(amount - deductible, 0)
    covered = int(eligible_base * percent / 100)
    per_visit_limit = int(getattr(rule, "per_visit_limit", 0) or 0)
    if per_visit_limit:
        covered = min(covered, per_visit_limit)

    annual_limit = int(getattr(rule, "annual_limit", 0) or policy.annual_limit or 0)
    used = 0
    if annual_limit:
        year_start = today.replace(month=1, day=1)
        used = int(
            InsuranceClaim.objects.filter(
                coverage=coverage,
                status__in=[
                    InsuranceClaim.Status.APPROVED,
                    InsuranceClaim.Status.PARTIALLY_APPROVED,
                    InsuranceClaim.Status.PAID,
                ],
                reviewed_at__date__gte=year_start,
            ).aggregate(total=Sum("approved_amount"))["total"]
            or 0
        )
        covered = min(covered, max(annual_limit - used, 0))

    copay_percent = rule.copay_percent if rule and rule.copay_percent is not None else policy.copay_percent
    copay_fixed = int(getattr(rule, "copay_fixed", 0) or policy.copay_fixed or 0)
    copay = int(amount * int(copay_percent or 0) / 100) + copay_fixed
    covered = max(min(covered - copay, amount), 0)
    requires_preauthorization = bool(
        policy.requires_preauthorization or (rule and rule.requires_preauthorization)
    )
    return {
        "result": InsuranceEligibilityCheck.Result.ELIGIBLE,
        "reason": "Coverage is active for the requested service.",
        "coverage_percent": percent,
        "covered_amount": covered,
        "patient_responsibility": max(amount - covered, 0),
        "requires_preauthorization": requires_preauthorization,
        "annual_limit": annual_limit,
        "annual_used": used,
        "deductible": deductible,
        "copay": copay,
        "rule_id": getattr(rule, "id", None),
    }


class PolicyListCreateView(APIView):
    allowed_roles = INSURANCE_REVIEW_ROLES

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsRole()]

    def get(self, request):
        qs = InsurancePolicy.objects.prefetch_related("benefit_rules").order_by("name")
        provider = request.query_params.get("provider")
        search = request.query_params.get("search")
        active = request.query_params.get("active")
        account = provider_account_for(request.user, User.Role.INSURANCE) if request.user.is_authenticated else None
        if account is not None and not provider:
            qs = qs.filter(provider=account)
        if provider:
            qs = qs.filter(provider_id=provider)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if active in {"true", "false"}:
            qs = qs.filter(active=active == "true")
        return Response(InsurancePolicySerializer(qs, many=True).data)

    def post(self, request):
        ser = InsurancePolicySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        insurance_account = _insurance_account(request)
        if insurance_account is None:
            return err("Your account is not assigned to this insurer workspace.", drf_status.HTTP_403_FORBIDDEN)
        policy = ser.save(provider=insurance_account)
        _audit_insurance(request, "insurance.policy.created", policy)
        return Response(InsurancePolicySerializer(policy).data, status=drf_status.HTTP_201_CREATED)


class PolicyDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REVIEW_ROLES

    def _get_own(self, request, pk):
        insurance_account = _insurance_account(request)
        if insurance_account is None:
            return None
        return InsurancePolicy.objects.filter(pk=pk, provider=insurance_account).prefetch_related("benefit_rules").first()

    def put(self, request, pk):
        policy = self._get_own(request, pk)
        if policy is None:
            return err("Policy not found.", drf_status.HTTP_404_NOT_FOUND)
        ser = InsurancePolicySerializer(policy, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        _audit_insurance(request, "insurance.policy.updated", policy)
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        policy = self._get_own(request, pk)
        if policy is None:
            return err("Policy not found.", drf_status.HTTP_404_NOT_FOUND)
        policy.active = False
        policy.save(update_fields=["active", "updated_at"])
        _audit_insurance(request, "insurance.policy.deactivated", policy)
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class BenefitRuleListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REVIEW_ROLES

    def _policy(self, request, policy_id):
        account = _insurance_account(request)
        return InsurancePolicy.objects.filter(pk=policy_id, provider=account).first() if account else None

    def get(self, request, policy_id):
        policy = self._policy(request, policy_id)
        if not policy:
            return err("Policy not found.", drf_status.HTTP_404_NOT_FOUND)
        return Response(InsuranceBenefitRuleSerializer(policy.benefit_rules.all(), many=True).data)

    def post(self, request, policy_id):
        policy = self._policy(request, policy_id)
        if not policy:
            return err("Policy not found.", drf_status.HTTP_404_NOT_FOUND)
        serializer = InsuranceBenefitRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save(policy=policy)
        _audit_insurance(request, "insurance.benefit_rule.created", rule)
        return Response(InsuranceBenefitRuleSerializer(rule).data, status=201)


class BenefitRuleDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REVIEW_ROLES

    def _rule(self, request, pk):
        account = _insurance_account(request)
        return InsuranceBenefitRule.objects.filter(pk=pk, policy__provider=account).first() if account else None

    def patch(self, request, pk):
        rule = self._rule(request, pk)
        if not rule:
            return err("Benefit rule not found.", 404)
        serializer = InsuranceBenefitRuleSerializer(rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _audit_insurance(request, "insurance.benefit_rule.updated", rule)
        return Response(serializer.data)

    put = patch

    def delete(self, request, pk):
        rule = self._rule(request, pk)
        if not rule:
            return err("Benefit rule not found.", 404)
        rule.active = False
        rule.save(update_fields=["active", "updated_at"])
        return Response(status=204)


class CoverageVerifyView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REQUEST_ROLES

    @transaction.atomic
    def post(self, request):
        member_id = str(request.data.get("member_id", "")).strip()
        provider_id = request.data.get("provider_id")
        if not member_id or not provider_id:
            return err("member_id and provider_id are required.")
        provider = User.objects.filter(
            pk=provider_id, role=User.Role.INSURANCE, is_active=True
        ).first()
        if provider is None:
            return err("Active insurance provider not found.", drf_status.HTTP_404_NOT_FOUND)
        try:
            estimated_amount = max(int(request.data.get("estimated_amount") or 0), 0)
        except (TypeError, ValueError):
            return err("estimated_amount must be a whole number greater than or equal to zero.")
        coverage = (
            PatientCoverage.objects.filter(member_id__iexact=member_id, provider=provider)
            .select_related("policy", "patient", "provider")
            .order_by("-active", "-id")
            .first()
        )
        if coverage is None:
            result = InsuranceEligibilityCheck.objects.create(
                provider=provider,
                member_id=member_id,
                service_code=str(request.data.get("service_code", "")),
                service_category=str(request.data.get("service_category", "")),
                estimated_amount=estimated_amount,
                result=InsuranceEligibilityCheck.Result.NOT_FOUND,
                reason="No matching member coverage was found.",
                requested_by=request.user,
            )
            return Response({"valid": False, **InsuranceEligibilityCheckSerializer(result).data})

        if request_role(request) == User.Role.PATIENT and coverage.patient_id != request.user.id:
            return err("You may only verify your own coverage.", drf_status.HTTP_403_FORBIDDEN)
        decision = _evaluate_coverage(
            coverage,
            service_code=str(request.data.get("service_code", "")),
            service_category=str(request.data.get("service_category", "")),
            estimated_amount=estimated_amount,
        )
        check = InsuranceEligibilityCheck.objects.create(
            coverage=coverage,
            patient=coverage.patient,
            provider=coverage.provider,
            member_id=coverage.member_id,
            service_code=str(request.data.get("service_code", "")),
            service_category=str(request.data.get("service_category", "")),
            estimated_amount=estimated_amount,
            result=decision["result"],
            coverage_percent=decision.get("coverage_percent", 0),
            covered_amount=decision.get("covered_amount", 0),
            patient_responsibility=decision.get("patient_responsibility", 0),
            requires_preauthorization=decision.get("requires_preauthorization", False),
            reason=decision.get("reason", ""),
            response_snapshot=decision,
            requested_by=request.user,
        )
        coverage.last_eligibility_check_at = timezone.now()
        if decision["result"] == InsuranceEligibilityCheck.Result.ELIGIBLE:
            coverage.verified_at = timezone.now()
        coverage.save(update_fields=["last_eligibility_check_at", "verified_at"])
        _audit_insurance(request, "insurance.eligibility.checked", check, patient=coverage.patient)
        payload = InsuranceEligibilityCheckSerializer(check).data
        payload.update(
            {
                "valid": decision["result"] == InsuranceEligibilityCheck.Result.ELIGIBLE,
                "policy": coverage.policy.name,
                "coverage_percent": decision.get("coverage_percent", 0),
            }
        )
        return Response(payload)


class EligibilityHistoryView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REQUEST_ROLES

    def get(self, request):
        qs = InsuranceEligibilityCheck.objects.select_related("coverage__policy", "patient", "provider")
        if request_role(request) == User.Role.PATIENT:
            qs = qs.filter(patient=request.user)
        elif request_role(request) != User.Role.ADMIN:
            account = provider_account_for(request.user, User.Role.INSURANCE)
            if account:
                qs = qs.filter(provider=account)
            else:
                organization = organization_for_user(request.user)
                if organization:
                    qs = qs.filter(requested_by__staff_memberships__organization=organization).distinct()
                else:
                    qs = qs.filter(requested_by=request.user)
        return Response(InsuranceEligibilityCheckSerializer(qs[:250], many=True).data)


class CoverageListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT, *INSURANCE_REVIEW_ROLES]

    def get(self, request):
        if request_role(request) == User.Role.PATIENT:
            qs = PatientCoverage.objects.filter(patient=request.user)
        else:
            account = _insurance_account(request)
            qs = PatientCoverage.objects.filter(provider=account) if account else PatientCoverage.objects.none()
            patient_id = request.query_params.get("patient")
            if patient_id:
                qs = qs.filter(patient_id=patient_id)
        qs = qs.select_related("policy", "provider", "patient").order_by("-active", "-id")
        return Response(PatientCoverageSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        provider_id = request.data.get("provider_id")
        policy_id = request.data.get("policy_id")
        member_id = str(request.data.get("member_id", "")).strip()
        if not member_id:
            return err("member_id is required.")
        provider = User.objects.filter(pk=provider_id, role=User.Role.INSURANCE, is_active=True).first()
        if provider is None:
            return err("Provider not found.", drf_status.HTTP_404_NOT_FOUND)
        if request_role(request) not in {User.Role.PATIENT, User.Role.ADMIN} and provider_account_for(request.user, User.Role.INSURANCE) != provider:
            return err("You cannot enrol members for this insurer.", 403)
        patient = request.user if request_role(request) == User.Role.PATIENT else User.objects.filter(
            pk=request.data.get("patient_id"), role=User.Role.PATIENT
        ).first()
        if patient is None:
            return err("Patient not found.", 404)
        policy = InsurancePolicy.objects.filter(pk=policy_id, provider=provider, active=True).first()
        if policy is None:
            return err("Active policy not found.", drf_status.HTTP_404_NOT_FOUND)
        if PatientCoverage.objects.filter(provider=provider, member_id__iexact=member_id, active=True).exclude(patient=patient).exists():
            return err("This member ID is already assigned to another active patient.", 409)
        coverage, _ = PatientCoverage.objects.update_or_create(
            patient=patient,
            provider=provider,
            policy=policy,
            defaults={
                "member_id": member_id,
                "active": True,
                "effective_from": request.data.get("effective_from") or timezone.localdate(),
                "expires_on": request.data.get("expires_on") or None,
                "dependant_code": str(request.data.get("dependant_code", "")),
                "employer_or_group": str(request.data.get("employer_or_group", "")),
            },
        )
        _audit_insurance(request, "insurance.coverage.enrolled", coverage, patient=patient)
        return Response(PatientCoverageSerializer(coverage).data, status=drf_status.HTTP_201_CREATED)


class PreauthorizationListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REQUEST_ROLES

    def get(self, request):
        qs = InsurancePreauthorization.objects.select_related(
            "patient", "provider", "policy", "coverage", "reviewed_by"
        )
        if request_role(request) == User.Role.PATIENT:
            qs = qs.filter(patient=request.user)
        elif request_role(request) == User.Role.ADMIN:
            provider = request.query_params.get("provider")
            if provider:
                qs = qs.filter(provider_id=provider)
        else:
            account = provider_account_for(request.user, User.Role.INSURANCE)
            if account:
                qs = qs.filter(provider=account)
            else:
                qs = qs.filter(Q(requesting_facility=request.user) | Q(patient_id=request.query_params.get("patient")))
        status_value = request.query_params.get("status")
        if status_value:
            qs = qs.filter(status=status_value)
        return Response(InsurancePreauthorizationSerializer(qs[:250], many=True).data)

    @transaction.atomic
    def post(self, request):
        coverage = PatientCoverage.objects.select_related("patient", "provider", "policy").filter(
            pk=request.data.get("coverage_id")
        ).first()
        if coverage is None:
            return err("coverage_id is required and must identify an enrolled member.", 404)
        if request_role(request) == User.Role.PATIENT and coverage.patient_id != request.user.id:
            return err("You may request authorization only for your own coverage.", 403)
        if not coverage.is_current:
            return err("Coverage is not active.", 409)
        service_name = str(request.data.get("service_name", "")).strip()
        if not service_name:
            return err("service_name is required.")
        serializer = InsurancePreauthorizationSerializer(
            data={
                key: request.data[key]
                for key in [
                    "service_code", "service_name", "clinical_indication", "diagnosis_code",
                    "requested_amount",
                ]
                if key in request.data
            }
        )
        serializer.is_valid(raise_exception=True)
        preauthorization = serializer.save(
            patient=coverage.patient,
            provider=coverage.provider,
            policy=coverage.policy,
            coverage=coverage,
            requesting_facility=None if request_role(request) == User.Role.PATIENT else request.user,
            status=InsurancePreauthorization.Status.SUBMITTED,
        )
        _audit_insurance(request, "insurance.preauthorization.submitted", preauthorization, patient=coverage.patient)
        _notify_insurance(
            coverage.provider,
            "Preauthorization submitted",
            f"{coverage.patient.display_name} requested authorization for {service_name}.",
            action_url="/insurance/preauthorizations",
            metadata={"preauthorization_id": preauthorization.id},
        )
        return Response(InsurancePreauthorizationSerializer(preauthorization).data, status=201)


class PreauthorizationDecisionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REVIEW_ROLES

    @transaction.atomic
    def post(self, request, pk):
        account = _insurance_account(request)
        preauthorization = InsurancePreauthorization.objects.select_for_update().filter(pk=pk, provider=account).first()
        if not preauthorization:
            return err("Preauthorization not found.", 404)
        action = str(request.data.get("action", "")).lower()
        reason = str(request.data.get("reason", "")).strip()
        status_map = {
            "start_review": InsurancePreauthorization.Status.IN_REVIEW,
            "query": InsurancePreauthorization.Status.QUERY,
            "approve": InsurancePreauthorization.Status.APPROVED,
            "partial": InsurancePreauthorization.Status.PARTIALLY_APPROVED,
            "reject": InsurancePreauthorization.Status.REJECTED,
            "cancel": InsurancePreauthorization.Status.CANCELLED,
        }
        if action not in status_map:
            return err("action must be start_review, query, approve, partial, reject or cancel.")
        if action in {"query", "partial", "reject", "cancel"} and not reason:
            return err("A decision reason is required for this action.")
        approved_amount = int(request.data.get("approved_amount") or 0)
        if action == "approve" and not approved_amount:
            approved_amount = preauthorization.requested_amount
        if approved_amount > preauthorization.requested_amount:
            return err("approved_amount cannot exceed requested_amount.")
        preauthorization.status = status_map[action]
        preauthorization.approved_amount = approved_amount if action in {"approve", "partial"} else 0
        preauthorization.decision_reason = reason
        preauthorization.reviewed_by = request.user
        preauthorization.reviewed_at = timezone.now()
        if action in {"approve", "partial"}:
            preauthorization.valid_until = request.data.get("valid_until") or (timezone.localdate() + timedelta(days=30))
        preauthorization.save()
        _audit_insurance(
            request,
            f"insurance.preauthorization.{action}",
            preauthorization,
            patient=preauthorization.patient,
            metadata={"reason": reason, "approved_amount": approved_amount},
        )
        _notify_insurance(
            preauthorization.patient,
            f"Preauthorization {preauthorization.get_status_display().lower()}",
            f"Your request for {preauthorization.service_name} is {preauthorization.get_status_display().lower()}.",
            metadata={"preauthorization_id": preauthorization.id},
        )
        return Response(InsurancePreauthorizationSerializer(preauthorization).data)


class ClaimListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REQUEST_ROLES

    def get(self, request):
        qs = InsuranceClaim.objects.select_related(
            "policy", "provider", "patient", "coverage", "preauthorization", "reviewed_by"
        ).prefetch_related("items", "remittances")
        if request_role(request) == User.Role.PATIENT:
            qs = qs.filter(patient=request.user)
        elif request_role(request) == User.Role.ADMIN:
            patient_id = request.query_params.get("patient")
            provider_id = request.query_params.get("provider")
            if patient_id:
                qs = qs.filter(patient_id=patient_id)
            if provider_id:
                qs = qs.filter(provider_id=provider_id)
        else:
            account = provider_account_for(request.user, User.Role.INSURANCE)
            if account:
                qs = qs.filter(provider=account)
            else:
                qs = qs.filter(requested_by=request.user)
        return Response(InsuranceClaimSerializer(qs[:250], many=True).data)

    @transaction.atomic
    def post(self, request):
        coverage = PatientCoverage.objects.select_related("patient", "provider", "policy").filter(
            pk=request.data.get("coverage_id")
        ).first()
        if coverage is None:
            provider_id = request.data.get("provider_id")
            policy_id = request.data.get("policy_id")
            patient = request.user if request_role(request) == User.Role.PATIENT else User.objects.filter(
                pk=request.data.get("patient_id"), role=User.Role.PATIENT
            ).first()
            coverage = PatientCoverage.objects.select_related("patient", "provider", "policy").filter(
                patient=patient, provider_id=provider_id, policy_id=policy_id, active=True
            ).first()
        if coverage is None:
            return err("An active coverage_id is required.", 404)
        if request_role(request) == User.Role.PATIENT and coverage.patient_id != request.user.id:
            return err("You may submit only your own claim.", 403)
        if not coverage.is_current:
            return err("Coverage is not active.", 409)

        invoice = None
        invoice_id = request.data.get("invoice_id")
        if invoice_id not in (None, ""):
            from payments.models import Invoice

            invoice = Invoice.objects.prefetch_related("items").filter(pk=invoice_id, patient=coverage.patient).first()
            if invoice is None:
                return err("Invoice was not found for this patient.", 404)
        amount = int(request.data.get("amount") or (invoice.amount if invoice else 0))
        if amount <= 0:
            return err("Claim amount must be greater than zero.")

        preauthorization = None
        if request.data.get("preauthorization_id"):
            preauthorization = InsurancePreauthorization.objects.filter(
                pk=request.data["preauthorization_id"],
                coverage=coverage,
                status__in=[
                    InsurancePreauthorization.Status.APPROVED,
                    InsurancePreauthorization.Status.PARTIALLY_APPROVED,
                ],
            ).first()
            if preauthorization is None:
                return err("The selected preauthorization is not approved for this member.", 409)

        claim = InsuranceClaim.objects.create(
            patient=coverage.patient,
            provider=coverage.provider,
            policy=coverage.policy,
            coverage=coverage,
            preauthorization=preauthorization,
            invoice_id=invoice.id if invoice else None,
            amount=amount,
            diagnosis_code=str(request.data.get("diagnosis_code", "")),
            clinical_summary=str(request.data.get("clinical_summary", "")),
            requested_by=request.user,
            status=InsuranceClaim.Status.SUBMITTED,
        )
        payload_items = request.data.get("items") or []
        if invoice:
            payload_items = [
                {
                    "invoice_item_id": item.id,
                    "service_code": item.code,
                    "description": item.description,
                    "quantity": max(int(item.quantity), 1),
                    "unit_price": item.unit_price,
                    "requested_amount": item.line_total,
                }
                for item in invoice.items.all()
            ]
        if not payload_items:
            payload_items = [{"description": "Healthcare services", "requested_amount": amount, "unit_price": amount, "quantity": 1}]
        for row in payload_items:
            InsuranceClaimItem.objects.create(
                claim=claim,
                invoice_item_id=row.get("invoice_item_id"),
                service_code=str(row.get("service_code", "")),
                description=str(row.get("description") or "Healthcare service"),
                quantity=max(int(row.get("quantity") or 1), 1),
                unit_price=max(int(row.get("unit_price") or row.get("requested_amount") or 0), 0),
                requested_amount=max(int(row.get("requested_amount") or 0), 0),
            )
        _audit_insurance(request, "insurance.claim.submitted", claim, patient=coverage.patient)
        _notify_insurance(
            coverage.provider,
            "New claim submitted",
            f"Claim {claim.claim_number} for {coverage.patient.display_name} requires review.",
            action_url="/insurance/claims",
            metadata={"claim_id": claim.id},
        )
        return Response(InsuranceClaimSerializer(claim).data, status=drf_status.HTTP_201_CREATED)


class ClaimManageView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REVIEW_ROLES

    def get(self, request):
        account = _insurance_account(request)
        qs = InsuranceClaim.objects.filter(provider=account) if account else InsuranceClaim.objects.none()
        status_value = request.query_params.get("status")
        search = request.query_params.get("search")
        if status_value:
            qs = qs.filter(status=status_value)
        if search:
            qs = qs.filter(
                Q(claim_number__icontains=search)
                | Q(patient__first_name__icontains=search)
                | Q(patient__last_name__icontains=search)
                | Q(patient__email__icontains=search)
            )
        qs = qs.select_related("policy", "patient", "reviewed_by").prefetch_related("items", "remittances")
        return Response(InsuranceClaimSerializer(qs[:500], many=True).data)


class ClaimDecideView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INSURANCE_REVIEW_ROLES

    @transaction.atomic
    def post(self, request, pk):
        account = _insurance_account(request)
        claim = InsuranceClaim.objects.select_for_update().filter(pk=pk, provider=account).first()
        if claim is None:
            return err("Claim not found.", drf_status.HTTP_404_NOT_FOUND)
        action = str(request.data.get("action", "")).lower()
        reason = str(request.data.get("reason", "")).strip()
        status_map = {
            "start_review": InsuranceClaim.Status.IN_REVIEW,
            "query": InsuranceClaim.Status.QUERY,
            "approve": InsuranceClaim.Status.APPROVED,
            "partial": InsuranceClaim.Status.PARTIALLY_APPROVED,
            "reject": InsuranceClaim.Status.REJECTED,
            "cancel": InsuranceClaim.Status.CANCELLED,
        }
        if action == "mark_paid":
            return self._mark_paid(request, claim)
        if action not in status_map:
            return err("action must be start_review, query, approve, partial, reject, cancel or mark_paid.")
        if action in {"query", "partial", "reject", "cancel"} and not reason:
            return err("A reason is required for this decision.")
        approved_amount = int(request.data.get("approved_amount") or 0)
        if action == "approve" and approved_amount == 0:
            approved_amount = claim.amount
        if approved_amount > claim.amount:
            return err("approved_amount cannot exceed the requested amount.")
        claim.status = status_map[action]
        claim.approved_amount = approved_amount if action in {"approve", "partial"} else 0
        claim.patient_responsibility = max(claim.amount - claim.approved_amount, 0)
        claim.decision_reason = reason
        claim.reviewed_by = request.user
        claim.reviewed_at = timezone.now()
        claim.save()

        item_decisions = request.data.get("items") or []
        by_id = {str(row.get("id")): row for row in item_decisions}
        if by_id:
            for item in claim.items.all():
                row = by_id.get(str(item.id))
                if not row:
                    continue
                item.approved_amount = min(int(row.get("approved_amount") or 0), item.requested_amount)
                item.status = str(row.get("status") or (
                    InsuranceClaimItem.Status.APPROVED if item.approved_amount == item.requested_amount
                    else InsuranceClaimItem.Status.PARTIALLY_APPROVED if item.approved_amount
                    else InsuranceClaimItem.Status.REJECTED
                ))
                item.reason = str(row.get("reason", ""))
                item.save()
        elif action in {"approve", "partial", "reject"}:
            remaining = claim.approved_amount
            for item in claim.items.all():
                item.approved_amount = min(item.requested_amount, remaining)
                remaining -= item.approved_amount
                item.status = (
                    InsuranceClaimItem.Status.APPROVED if item.approved_amount == item.requested_amount
                    else InsuranceClaimItem.Status.PARTIALLY_APPROVED if item.approved_amount
                    else InsuranceClaimItem.Status.REJECTED
                )
                item.reason = reason
                item.save()

        _audit_insurance(
            request,
            f"insurance.claim.{action}",
            claim,
            patient=claim.patient,
            metadata={"reason": reason, "approved_amount": claim.approved_amount},
        )
        _notify_insurance(
            claim.patient,
            f"Claim {claim.get_status_display().lower()}",
            f"Claim {claim.claim_number} is {claim.get_status_display().lower()}.",
            metadata={"claim_id": claim.id},
        )
        return Response(InsuranceClaimSerializer(claim).data)

    def _mark_paid(self, request, claim):
        if claim.status not in {InsuranceClaim.Status.APPROVED, InsuranceClaim.Status.PARTIALLY_APPROVED}:
            return err("Only approved claims can be remitted.", 409)
        paid_amount = int(request.data.get("paid_amount") or claim.approved_amount)
        if paid_amount <= 0 or paid_amount > claim.approved_amount:
            return err("paid_amount must be greater than zero and cannot exceed the approved amount.")
        payment_reference = str(request.data.get("payment_reference", "")).strip()
        if not payment_reference:
            return err("payment_reference is required.")
        remittance_number = str(request.data.get("remittance_number", "")).strip() or f"REM-{timezone.now():%Y%m%d}-{claim.id}"
        remittance = InsuranceRemittance.objects.create(
            provider=claim.provider,
            claim=claim,
            remittance_number=remittance_number,
            paid_amount=paid_amount,
            payment_reference=payment_reference,
            paid_on=request.data.get("paid_on") or timezone.localdate(),
            notes=str(request.data.get("notes", "")),
            created_by=request.user,
        )
        total_paid = claim.remittances.aggregate(total=Sum("paid_amount"))["total"] or 0
        if total_paid >= claim.approved_amount:
            claim.status = InsuranceClaim.Status.PAID
            claim.paid_at = timezone.now()
            claim.save(update_fields=["status", "paid_at", "updated_at"])
        _audit_insurance(request, "insurance.remittance.created", remittance, patient=claim.patient)
        _notify_insurance(
            claim.patient,
            "Insurance remittance recorded",
            f"Payment of {paid_amount:,} UGX was recorded for claim {claim.claim_number}.",
            metadata={"claim_id": claim.id, "remittance_id": remittance.id},
        )
        return Response(InsuranceClaimSerializer(claim).data)


class RemittanceListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT, *INSURANCE_REVIEW_ROLES]

    def get(self, request):
        qs = InsuranceRemittance.objects.select_related("claim__patient", "provider", "created_by")
        if request_role(request) == User.Role.PATIENT:
            qs = qs.filter(claim__patient=request.user)
        elif request_role(request) != User.Role.ADMIN:
            account = provider_account_for(request.user, User.Role.INSURANCE)
            qs = qs.filter(provider=account) if account else qs.none()
        return Response(InsuranceRemittanceSerializer(qs[:500], many=True).data)
