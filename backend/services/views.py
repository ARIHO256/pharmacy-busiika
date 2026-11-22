from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status as drf_status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole
from workforce.access import organization_for_user

from .models import (
    Bed,
    CartItem,
    HospitalBooking,
    HospitalService,
    InsuranceClaim,
    InsurancePolicy,
    CriticalResultAcknowledgement,
    LabOrder,
    LabResult,
    LabTest,
    Medicine,
    Order,
    OrderItem,
    PatientCoverage,
    PharmacyOrder,
    Supplier,
)
from .serializers import (
    BedSerializer,
    CartItemSerializer,
    HospitalBookingSerializer,
    HospitalServiceSerializer,
    InsuranceClaimSerializer,
    InsurancePolicySerializer,
    LabOrderSerializer,
    LabResultSerializer,
    LabTestSerializer,
    MedicineSerializer,
    OrderSerializer,
    PatientCoverageSerializer,
    PharmacyOrderSerializer,
    ProviderDirectorySerializer,
    SupplierSerializer,
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
    if user.role in {User.Role.PHARMACIST, User.Role.LAB_TECHNICIAN} and not user.is_verified:
        return None
    if user.role == expected_role:
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
                ProviderProfile.objects.filter(status="verified", user__role=role, user__is_active=True)
                .select_related("user")
            )
            affiliations = {}
            registered = set()
            if role == User.Role.PHARMACY:
                from registry.models import Organization
                for organization in Organization.objects.filter(
                    owner_id__in=profiles.values("user_id"), organization_type=Organization.Type.PHARMACY,
                ).select_related("parent_facility"):
                    registered.add(organization.owner_id)
                    parent = organization.parent_facility
                    if organization.active and organization.status == Organization.Status.VERIFIED and (
                        not parent or parent.active and parent.status == Organization.Status.VERIFIED
                    ):
                        affiliations.setdefault(organization.owner_id, parent)
            for p in profiles:
                name = p.org_name or f"{p.user.first_name} {p.user.last_name}".strip() or p.user.email
                if p.user_id in registered and p.user_id not in affiliations:
                    continue
                row = {"id": p.user_id, "org_name": name, "address": p.address}
                parent = affiliations.get(p.user_id)
                if parent:
                    row.update(parent_facility_name=parent.legal_name, parent_facility_type=parent.organization_type)
                rows.append(row)
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
class MedicineTaxonomyView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["pharmacy", "pharmacist", "facility_manager", "storekeeper"]

    def get(self, request):
        from .taxonomy import catalogue

        account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        return Response(catalogue(account.pk))


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
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        ser = MedicineSerializer(data=request.data, context={"request": request, "pharmacy_id": pharmacy_account.pk})
        if not ser.is_valid():
            return err(str(ser.errors))
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

    @transaction.atomic
    def put(self, request, pk):
        med = self._get_own(request, pk)
        if med is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        med = Medicine.objects.select_for_update().get(pk=med.pk)
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
        if med.batches.exists():
            return err("Medicines with batch history cannot be deleted.", 409)
        try:
            med.delete()
        except ProtectedError:
            return err("This medicine is referenced in pharmacy records and cannot be deleted.", 409)
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
        from operations.services import online_orderable_batches
        if not online_orderable_batches(medicine).filter(quantity__gt=0).exists():
            return err("Online ordering requires classified OTC stock in an available batch at a verified pharmacy.", 409)
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

    @transaction.atomic
    def post(self, request):
        delivery = bool(request.data.get("delivery", False))
        address = request.data.get("address", "") or ""
        if delivery and not address:
            return err("address is required when delivery is requested.")
        User.objects.select_for_update().get(pk=request.user.pk)
        cart = list(CartItem.objects.filter(patient=request.user).select_related("medicine").order_by("medicine_id"))
        if not cart:
            return err("Cart is empty.")

        locked_medicines = {med.pk: med for med in Medicine.objects.select_for_update().filter(pk__in=[item.medicine_id for item in cart]).order_by("pk")}
        for item in cart:
            item.medicine = locked_medicines[item.medicine_id]

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
                from operations.services import allocate_order_stock
                allocate_order_stock(i.medicine, i.qty, request.user, order.pk)
            orders.append(order)

        CartItem.objects.filter(patient=request.user).delete()
        return Response(
            OrderSerializer(orders, many=True, context={"request": request}).data,
            status=drf_status.HTTP_201_CREATED,
        )


class OrderListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT, User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.CASHIER]

    def get(self, request):
        if request.user.role == User.Role.CASHIER:
            from .pharmacy_sales import staff_pharmacy
            qs = Order.objects.filter(pharmacy_id=staff_pharmacy(request.user).owner_id)
        elif request.user.role in {User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER}:
            pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
            if denied:
                return denied
            qs = Order.objects.filter(pharmacy=pharmacy_account)
        else:
            qs = Order.objects.filter(patient=request.user)
        qs = qs.prefetch_related("items").order_by("-created_at")
        return Response(OrderSerializer(qs, many=True, context={"request": request}).data)


HANDOVER_FIELDS = ["handed_over_at", "handover_reference", "handed_over_by"]


def record_handover(request, order):
    from operations.serializers import StrictSerializer
    from operations.views import validated

    class HandoverInput(StrictSerializer):
        status = serializers.CharField()
        handover_reference = serializers.CharField(max_length=200)

    values = validated(HandoverInput, request)
    ensure_handover_stock_safe(order)
    order.handed_over_at = timezone.now()
    order.handed_over_by = request.user
    order.handover_reference = values["handover_reference"]


def ensure_handover_stock_safe(order):
    from operations.models import MedicineBatch
    movements = order.stock_movements if isinstance(order, Order) else order.dispensing_movements
    active_dispenses = movements.filter(kind="dispensed", reversal__isnull=True)
    batch_ids = active_dispenses.values_list("batch_id", flat=True)
    batches = list(MedicineBatch.objects.select_for_update().filter(pk__in=batch_ids).order_by("pk"))
    if any(batch.status != "available" or batch.expires_on <= timezone.localdate() for batch in batches):
        raise ValidationError("The order contains expired, recalled or quarantined stock. Resolve the stock issue before handover.")


class OrderUpdateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]
    ALLOWED = {Order.Status.CONFIRMED, Order.Status.READY, Order.Status.DISPATCHED, Order.Status.DELIVERED, Order.Status.CANCELLED}

    @transaction.atomic
    def post(self, request, pk):
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        order = Order.objects.select_for_update().filter(pk=pk, pharmacy=pharmacy_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        new_status = request.data.get("status")
        if new_status not in self.ALLOWED:
            return err("Select a valid order status.")
        if new_status == order.status:
            return Response(OrderSerializer(order, context={"request": request}).data)
        transitions = {
            "pending": {"confirmed", "cancelled"},
            "confirmed": {"dispatched" if order.delivery else "ready", "cancelled"},
            "ready": {"delivered", "cancelled"},
            "dispatched": {"delivered"},
        }
        if new_status not in transitions.get(order.status, set()):
            return err("This order cannot make that status transition.", 409)
        from operations.services import event, restore_order_stock
        if new_status == "cancelled":
            if order.invoice_id:
                return err("This order has a recorded payment and cannot be cancelled here.", 409)
            restore_order_stock(order, request.user)
        order.status = new_status
        fields = ["status"]
        if new_status in {"ready", "dispatched"}:
            ensure_handover_stock_safe(order)
        if new_status == "delivered":
            record_handover(request, order)
            fields += HANDOVER_FIELDS
        order.save(update_fields=fields)
        event(order, request.user, "order.transition", status=new_status)
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
    allowed_roles = [User.Role.PHARMACY, User.Role.PHARMACIST, User.Role.FACILITY_MANAGER, User.Role.STOREKEEPER]
    ALLOWED = {
        PharmacyOrder.Status.PREPARED,
        PharmacyOrder.Status.DELIVERED,
        PharmacyOrder.Status.REJECTED,
    }

    def get(self, request, pk):
        from operations.access import organizations, require_role
        from operations.models import MedicineBatch

        require_role(request.user, {"pharmacist"})
        pharmacy, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        order = get_object_or_404(PharmacyOrder, pk=pk, pharmacy=pharmacy)
        prescription = order.get_prescription()
        if prescription is None or prescription.patient_id != order.patient_id:
            return err("No valid prescription is linked to this order.", 409)
        substitutions = dict(order.substitutions.filter(status="approved", prescription_version=prescription.version)
                             .values_list("item_id", "replacement_id"))
        names = {item.medicine_name.strip().casefold() for item in prescription.items.all() if item.pk not in substitutions}
        replacements = set(substitutions.values())
        scope = organizations(request.user).filter(owner=pharmacy)
        batches = MedicineBatch.objects.filter(
            organization__in=scope, status="available", quantity__gt=0, expires_on__gt=timezone.localdate(),
        ).select_related("medicine").order_by("expires_on", "pk")
        return Response([{
            "id": batch.pk, "medicine_name": batch.medicine.name, "batch_number": batch.batch_number,
            "quantity": batch.quantity, "expires_on": batch.expires_on, "controlled": batch.controlled,
            "medicine": batch.medicine_id,
        } for batch in batches if batch.medicine_id in replacements or batch.medicine.name.strip().casefold() in names])

    @transaction.atomic
    def post(self, request, pk):
        pharmacy_account, denied = require_provider_account(request, User.Role.PHARMACY)
        if denied:
            return denied
        order = PharmacyOrder.objects.select_for_update().filter(pk=pk, pharmacy=pharmacy_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        new_status = request.data.get("status")
        if new_status == "dispense":
            return self.dispense(request, order)
        if new_status == "reverse_dispense":
            return self.reverse_dispense(request, order)
        if new_status not in self.ALLOWED:
            return err("status must be one of prepared|delivered|rejected.")
        if new_status != order.status and new_status not in {
            PharmacyOrder.Status.NEW: {PharmacyOrder.Status.PREPARED, PharmacyOrder.Status.REJECTED},
            PharmacyOrder.Status.PREPARED: {PharmacyOrder.Status.DELIVERED},
        }.get(order.status, set()):
            return err("This prescription order cannot make that status transition.", 409)
        if new_status == PharmacyOrder.Status.DELIVERED:
            prescription = order.get_prescription()
            if not prescription or prescription.patient_id != order.patient_id:
                return err("No valid prescription is linked to this order.", 409)
            if order.status != PharmacyOrder.Status.DELIVERED:
                quantities = {
                    row["prescription_item_id"]: -row["quantity"]
                    for row in order.dispensing_movements.filter(kind="dispensed", reversal__isnull=True)
                    .values("prescription_item_id").annotate(quantity=Sum("quantity"))
                }
                items = list(prescription.items.all())
                if (prescription.status != "dispensed" or not items
                        or any(quantities.get(item.pk, 0) != item.quantity for item in items)):
                    return err("Complete dispensing on this pharmacy order before recording handover.", 409)
        if new_status == "delivered":
            from operations.access import require_role
            require_role(request.user, {"pharmacist"})
        order.status = new_status
        fields = ["status"]
        if new_status == "delivered" and order.handed_over_at is None:
            record_handover(request, order)
            fields += HANDOVER_FIELDS
        order.save(update_fields=fields)
        return Response(PharmacyOrderSerializer(order, context={"request": request}).data)


    def dispense(self, request, order):
        from operations.access import organizations, require_role
        from operations.models import MedicineBatch
        from operations.services import move_stock

        require_role(request.user, {"pharmacist"})
        if order.status != PharmacyOrder.Status.PREPARED:
            return err("The prescription order must be prepared for dispensing.", 409)
        prescription = order.get_prescription()
        if prescription is None or prescription.patient_id != order.patient_id:
            return err("No valid prescription is linked to this order.", 409)

        class DispenseInput(serializers.Serializer):
            item = serializers.IntegerField(min_value=1)
            batch = serializers.IntegerField(min_value=1)
            quantity = serializers.IntegerField(min_value=1)
            reason = serializers.CharField(max_length=2000)
            reference = serializers.UUIDField()
            witness = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)
            alerts_reviewed = serializers.BooleanField(default=False)

        data = DispenseInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        item = get_object_or_404(prescription.items.all(), pk=values["item"])
        batch = get_object_or_404(
            MedicineBatch, pk=values["batch"],
            organization__in=organizations(request.user).filter(owner=order.pharmacy),
        )
        if batch.medicine.sale_type == Medicine.SaleType.UNCLASSIFIED:
            return err("Classify this product before dispensing.", 409)
        if batch.medicine.sale_type == Medicine.SaleType.CONTROLLED and not batch.controlled:
            return err("Use a controlled batch for a controlled product.", 409)
        if not hasattr(order, "safety_review") or order.safety_review.prescription_version != prescription.version:
            return err("Record pharmacist review and counselling before dispensing.", 409)
        if order.safety_review.product_ids.get(str(item.pk)) != batch.medicine_id:
            return err("Select a batch of the product verified during pharmacist review.", 409)
        if order.safety_review.medication_check.get("alerts") and not values["alerts_reviewed"]:
            return err("Review the recorded medication alerts before dispensing.", 409)
        move_stock(batch, request.user, quantity=-values["quantity"], kind="dispensed",
                   reason=values["reason"], reference=values["reference"], patient=order.patient,
                   witness=values.get("witness"), prescription_item=item, pharmacy_order=order)
        return Response(PharmacyOrderSerializer(order, context={"request": request}).data)


    def reverse_dispense(self, request, order):
        from operations.access import require_role
        from operations.services import reverse_unhanded_dispense

        require_role(request.user, {"pharmacist"})
        if order.status != PharmacyOrder.Status.PREPARED:
            return err("Only a prepared order can have an unhanded dispensing reversed.", 409)

        class ReversalInput(serializers.Serializer):
            movement = serializers.IntegerField(min_value=1)
            reason = serializers.CharField(max_length=2000)
            unhanded = serializers.BooleanField()
            witness = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)

        serializer = ReversalInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if not values["unhanded"]:
            return err("Confirm the medicine never left pharmacy custody.")
        movement = get_object_or_404(
            order.dispensing_movements.select_related("batch", "prescription_item"),
            pk=values["movement"], kind="dispensed", prescription_item__isnull=False,
        )
        reverse_unhanded_dispense(movement, request.user, reason=values["reason"], witness=values.get("witness"))
        return Response(PharmacyOrderSerializer(order, context={"request": request}).data)


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
        ser = SupplierSerializer(data=request.data, context={"request": request})
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
        ser = SupplierSerializer(supplier, data=request.data, partial=True, context={"request": request})
        if not ser.is_valid():
            return err(str(ser.errors))
        ser.save()
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        supplier = self._get_own(request, pk)
        if supplier is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        try:
            supplier.delete()
        except ProtectedError:
            return err("This supplier is referenced in purchasing or inventory records and cannot be deleted.", 409)
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# LAB
# ---------------------------------------------------------------------------
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
    allowed_roles = [User.Role.PATIENT, User.Role.DOCTOR, User.Role.NURSE]

    def get(self, request):
        if request.user.role == User.Role.PATIENT:
            qs = LabOrder.objects.filter(patient=request.user)
        else:
            from operations.access import organizations
            scope = organizations(request.user)
            if request.user.role == User.Role.DOCTOR:
                qs = LabOrder.objects.filter(
                    Q(referring_doctor=request.user) | Q(visit__assigned_doctor=request.user, visit__organization__in=scope)
                )
            else:
                qs = LabOrder.objects.filter(visit__assigned_nurse=request.user, visit__organization__in=scope)
        qs = qs.select_related("test", "lab", "patient", "referring_doctor", "visit").order_by("-created_at")
        return Response(LabOrderSerializer(qs, many=True, context={"request": request}).data)

    @transaction.atomic
    def post(self, request):
        lab_id = request.data.get("lab_id") or request.data.get("lab")
        test_id = request.data.get("test_id") or request.data.get("test")
        lab = User.objects.filter(pk=lab_id, role=User.Role.LAB, is_verified=True).first()
        if lab is None:
            return err("A verified laboratory is required.", drf_status.HTTP_404_NOT_FOUND)
        test = LabTest.objects.filter(pk=test_id, lab=lab).first()
        if test is None:
            return err("Test not found for the selected laboratory.", drf_status.HTTP_404_NOT_FOUND)
        visit = None
        if request.user.role == User.Role.PATIENT:
            patient = request.user
            referring_doctor = None
        else:
            patient_id = request.data.get("patient_id") or request.data.get("patient")
            patient = User.objects.filter(pk=patient_id, role=User.Role.PATIENT).first()
            if patient is None:
                return err("patient_id is required for a clinical referral.")
            if request.user.role != User.Role.DOCTOR or not request.user.is_verified:
                return err("A verified ordering doctor is required.", 403)
            from clinical.services import can_access_patient
            from operations.access import organizations
            from workforce.models import PatientVisit

            visit_id = request.data.get("visit_id")
            if visit_id:
                visit = get_object_or_404(
                    PatientVisit.objects.select_for_update().filter(
                        patient=patient, assigned_doctor=request.user, organization__in=organizations(request.user),
                    ).exclude(status__in=[PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED]),
                    pk=visit_id,
                )
            elif not can_access_patient(request.user, patient)[0]:
                return err("Select an assigned visit or a patient with an authorized care relationship.", 403)
            referring_doctor = request.user
        order = LabOrder.objects.create(
            patient=patient,
            visit=visit,
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
        if visit and visit.status in {PatientVisit.Status.IN_CONSULTATION, PatientVisit.Status.WAITING_CLINICIAN}:
            visit.status = PatientVisit.Status.LABORATORY
            visit.save(update_fields=["status", "updated_at"])
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
        qs = LabOrder.objects.filter(lab=lab_account).select_related("test", "patient", "referring_doctor", "visit").order_by("-created_at")
        return Response(LabOrderSerializer(qs, many=True, context={"request": request}).data)


class LabOrderUpdateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.LAB, User.Role.LAB_TECHNICIAN, User.Role.FACILITY_MANAGER]

    @transaction.atomic
    def post(self, request, pk):
        lab_account, denied = require_provider_account(request, User.Role.LAB)
        if denied:
            return denied
        order = LabOrder.objects.select_for_update().filter(pk=pk, lab=lab_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        if request.data.get("action") == "record_arrival":
            if order.arrived_at is None:
                if order.status not in {LabOrder.Status.BOOKED, LabOrder.Status.READY_FOR_COLLECTION}:
                    return err("This order is not awaiting check-in.", 409)
                from governance.services import audit
                order.arrived_at = timezone.now()
                order.save(update_fields=["arrived_at", "updated_at"])
                audit(actor=request.user, patient=order.patient, resource=order, purpose="treatment",
                      action="laboratory.arrival.recorded", request=request)
            return Response(LabOrderSerializer(order, context={"request": request}).data)
        previous_status = order.status
        changed = []
        new_status = request.data.get("status")
        if new_status:
            valid = {c for c, _ in LabOrder.Status.choices}
            if new_status not in valid:
                return err("Invalid status.")
            if new_status == LabOrder.Status.REJECTED:
                if previous_status not in {LabOrder.Status.SAMPLE_COLLECTED, LabOrder.Status.SAMPLE_RECEIVED} or order.result_released:
                    return err("Only collected or received specimens without a released result can be rejected.", 409)
                if not str(request.data.get("rejection_reason") or "").strip():
                    return err("Enter a specimen rejection reason.")
            if previous_status == LabOrder.Status.REJECTED:
                if new_status != LabOrder.Status.READY_FOR_COLLECTION:
                    return err("Request recollection before updating a rejected order.", 409)
                order.specimen_id = order.specimen_type = order.collection_notes = ""
                order.arrived_at = order.collected_at = order.received_at = order.collected_by = None
                changed.extend(["specimen_id", "specimen_type", "collection_notes", "collected_at", "received_at", "collected_by", "arrived_at"])
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
            if previous_status == LabOrder.Status.REJECTED and new_status == LabOrder.Status.READY_FOR_COLLECTION and field in {"specimen_id", "specimen_type", "collection_notes", "rejection_reason"}:
                continue
            if field in request.data:
                setattr(order, field, request.data.get(field) or "")
                changed.append(field)
        if "result_file" in request.FILES:
            order.result_file = request.FILES["result_file"]
            changed.append("result_file")
        if changed:
            order.save(update_fields=list(dict.fromkeys(changed + ["updated_at"])))
        if new_status == LabOrder.Status.REJECTED or previous_status == LabOrder.Status.REJECTED and new_status:
            from governance.services import audit
            audit(actor=request.user, patient=order.patient, resource=order, purpose="treatment",
                  action="laboratory.specimen.rejected" if new_status == LabOrder.Status.REJECTED else "laboratory.specimen.recollection_requested",
                  metadata={"order_id": order.pk}, request=request)
        if order.result_released and previous_status != order.status:
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
                if order.referring_doctor_id:
                    notify(order.referring_doctor, "Laboratory report available",
                           "A report is ready in the laboratory referrals worklist.",
                           kind="laboratory", action_url="/doctor/lab-referrals")
            except Exception:
                pass
        return Response(LabOrderSerializer(order, context={"request": request}).data)

class LabResultListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [
        User.Role.PATIENT, User.Role.LAB, User.Role.LAB_TECHNICIAN,
        User.Role.DOCTOR, User.Role.NURSE, User.Role.ADMIN,
    ]

    def _order_for_user(self, request, pk):
        order = LabOrder.objects.filter(pk=pk).select_related(
            "patient", "lab", "test", "referring_doctor"
        ).first()
        if order is None:
            return None, err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        allowed = (
            request.user.role == User.Role.ADMIN
            or request.user == order.patient
            or provider_account_for(request.user, User.Role.LAB) == order.lab
            or request.user == order.referring_doctor
        )
        if request.user.role == User.Role.DOCTOR and not allowed:
            from appointments.models import Appointment

            from operations.access import organizations
            allowed = bool(order.visit_id and order.visit.assigned_doctor_id == request.user.pk
                           and organizations(request.user).filter(pk=order.visit.organization_id).exists())
            if not allowed and not order.visit_id:
                allowed = Appointment.objects.filter(
                    doctor=request.user, patient=order.patient,
                ).exclude(status="cancelled").exists()
        elif request.user.role == User.Role.NURSE and not allowed:
            from workforce.models import PatientVisit

            from operations.access import organizations
            visits = PatientVisit.objects.filter(patient=order.patient, assigned_nurse=request.user).exclude(
                status__in=[PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED]
            )
            if order.visit_id:
                visits = visits.filter(pk=order.visit_id, organization__in=organizations(request.user))
            allowed = visits.exists()
        if not allowed:
            return None, err("Not allowed.", drf_status.HTTP_403_FORBIDDEN)
        return order, None

    def get(self, request, pk):
        order, denied = self._order_for_user(request, pk)
        if denied:
            return denied
        qs = order.results.select_related("replacement", "acknowledgement__acknowledged_by")
        if request.user.role == User.Role.PATIENT:
            if not order.result_released:
                return Response([])
            qs = qs.filter(status__in=[LabResult.Status.FINAL, LabResult.Status.AMENDED, LabResult.Status.CORRECTED])
        return Response(LabResultSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request, pk):
        if request.user.role not in {User.Role.LAB, User.Role.LAB_TECHNICIAN}:
            return err("Only authorized laboratory staff can enter results.", drf_status.HTTP_403_FORBIDDEN)
        lab_account, denied = require_provider_account(request, User.Role.LAB)
        if denied:
            return denied
        order = LabOrder.objects.select_for_update().filter(pk=pk, lab=lab_account).first()
        if order is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        if order.status == LabOrder.Status.REJECTED:
            return err("The specimen must be recollected before entering results.", 409)
        serializer = LabResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_status = serializer.validated_data.get("status", LabResult.Status.PRELIMINARY)
        previous = serializer.validated_data.get("supersedes")
        amendment = requested_status in {LabResult.Status.AMENDED, LabResult.Status.CORRECTED}
        if amendment:
            if not previous or previous.order_id != order.pk or not previous.released_at:
                return err("Select a released result from this order to amend.")
            if LabResult.objects.filter(supersedes=previous).exists():
                return err("This result has already been replaced.", 409)
            if not serializer.validated_data.get("amendment_reason", "").strip():
                return err("Enter a reason for the amendment.")
        elif previous:
            return err("A replacement must be an amended or corrected result.")
        elif order.results.filter(
            code=serializer.validated_data.get("code", ""), name=serializer.validated_data["name"], supersedes__isnull=True,
        ).exists():
            return err("A result with that name and code already exists. Amend its current version.", 409)
        release = str(request.data.get("release", "")).lower() in {"true", "1"} or requested_status in {
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
            order.status = LabOrder.Status.AMENDED if amendment else LabOrder.Status.COMPLETED
            order.result_released = True
            order.released_at = now
            fields = ["status", "result_released", "released_at", "updated_at"]
            if not amendment and "result_file" in request.FILES:
                order.result_file = request.FILES["result_file"]
                fields.append("result_file")
            if not amendment and "result_notes" in request.data:
                order.result_notes = request.data["result_notes"]
                fields.append("result_notes")
            order.save(update_fields=fields)
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
                        "Referred laboratory result amended" if amendment else "Referred laboratory result available",
                        f"{order.test.name} results for {order.patient.display_name} are ready.",
                        kind="laboratory",
                        priority="urgent" if result.interpretation == LabResult.Interpretation.CRITICAL else "normal",
                        action_url="/doctor/lab-referrals",
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
    allowed_roles = [User.Role.DOCTOR, User.Role.NURSE, User.Role.ADMIN]

    def post(self, request, pk):
        result = LabResult.objects.filter(pk=pk, interpretation=LabResult.Interpretation.CRITICAL, released_at__isnull=False, replacement__isnull=True).select_related("order__patient").first()
        if result is None:
            return err("Critical result not found.", drf_status.HTTP_404_NOT_FOUND)
        from operations.access import organizations, require_role
        require_role(request.user, {"doctor", "nurse"})
        order = result.order
        if request.user.role == User.Role.DOCTOR:
            from appointments.models import Appointment
            assigned = bool(order.visit_id and order.visit.assigned_doctor_id == request.user.pk
                            and organizations(request.user).filter(pk=order.visit.organization_id).exists())
            legacy = not order.visit_id and Appointment.objects.filter(
                doctor=request.user, patient=order.patient,
            ).exclude(status="cancelled").exists()
            if request.user.pk != order.referring_doctor_id and not assigned and not legacy:
                return err("No care relationship.", drf_status.HTTP_403_FORBIDDEN)
        if request.user.role == User.Role.NURSE:
            from workforce.models import PatientVisit
            visits = PatientVisit.objects.filter(patient=order.patient, assigned_nurse=request.user).exclude(
                status__in=[PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED],
            )
            if order.visit_id:
                visits = visits.filter(pk=order.visit_id, organization__in=organizations(request.user))
            if not visits.exists():
                return err("An active assigned visit is required.", drf_status.HTTP_403_FORBIDDEN)
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
        from operations.models import Admission
        if Admission.objects.filter(bed=bed).exists():
            return err("Beds linked to admission history cannot be deleted.", 409)
        bed.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class BedToggleView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.HOSPITAL, User.Role.RECEPTIONIST, User.Role.FACILITY_MANAGER]

    @transaction.atomic
    def post(self, request, pk):
        hospital_account, denied = require_provider_account(request, User.Role.HOSPITAL)
        if denied:
            return denied
        bed = Bed.objects.select_for_update().filter(pk=pk, hospital=hospital_account).first()
        if bed is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        from operations.models import Admission
        if Admission.objects.filter(bed=bed, status="admitted").exists():
            return err("Use the admission transfer or discharge workflow for this occupied bed.", 409)
        bed.is_occupied = not bed.is_occupied
        bed.save(update_fields=["is_occupied"])
        return Response(BedSerializer(bed).data)


# ---------------------------------------------------------------------------
# INSURANCE
# ---------------------------------------------------------------------------
class PolicyListCreateView(APIView):
    allowed_roles = [User.Role.INSURANCE, User.Role.INSURANCE_OFFICER, User.Role.FACILITY_MANAGER]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsRole()]

    def get(self, request):
        qs = InsurancePolicy.objects.all().order_by("id")
        provider = request.query_params.get("provider")
        search = request.query_params.get("search")
        if (
            request.user.is_authenticated
            and provider_account_for(request.user, User.Role.INSURANCE) is not None
            and not provider
        ):
            qs = qs.filter(provider=provider_account_for(request.user, User.Role.INSURANCE))
        if provider:
            qs = qs.filter(provider_id=provider)
        if search:
            qs = qs.filter(name__icontains=search)
        return Response(InsurancePolicySerializer(qs, many=True).data)

    def post(self, request):
        ser = InsurancePolicySerializer(data=request.data)
        if not ser.is_valid():
            return err(str(ser.errors))
        insurance_account, denied = require_provider_account(request, User.Role.INSURANCE)
        if denied:
            return denied
        policy = ser.save(provider=insurance_account)
        return Response(InsurancePolicySerializer(policy).data, status=drf_status.HTTP_201_CREATED)


class PolicyDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.INSURANCE, User.Role.INSURANCE_OFFICER, User.Role.FACILITY_MANAGER]

    def _get_own(self, request, pk):
        insurance_account = provider_account_for(request.user, User.Role.INSURANCE)
        if insurance_account is None:
            return None
        return InsurancePolicy.objects.filter(pk=pk, provider=insurance_account).first()

    def put(self, request, pk):
        policy = self._get_own(request, pk)
        if policy is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        ser = InsurancePolicySerializer(policy, data=request.data, partial=True)
        if not ser.is_valid():
            return err(str(ser.errors))
        ser.save()
        return Response(ser.data)

    patch = put

    def delete(self, request, pk):
        policy = self._get_own(request, pk)
        if policy is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        policy.delete()
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class CoverageVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        member_id = request.data.get("member_id")
        provider_id = request.data.get("provider_id")
        if not member_id or not provider_id:
            return err("member_id and provider_id are required.")
        coverage = (
            PatientCoverage.objects.filter(member_id=member_id, provider_id=provider_id, active=True)
            .select_related("policy")
            .first()
        )
        if coverage is None:
            return Response({"valid": False})
        return Response(
            {
                "valid": True,
                "policy": coverage.policy.name,
                "coverage_percent": coverage.policy.coverage_percent,
            }
        )


class CoverageListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT]

    def get(self, request):
        qs = (
            PatientCoverage.objects.filter(patient=request.user)
            .select_related("policy", "provider")
            .order_by("-id")
        )
        return Response(PatientCoverageSerializer(qs, many=True).data)

    def post(self, request):
        provider_id = request.data.get("provider_id")
        policy_id = request.data.get("policy_id")
        member_id = request.data.get("member_id")
        if not member_id:
            return err("member_id is required.")
        provider = User.objects.filter(pk=provider_id, role=User.Role.INSURANCE).first()
        if provider is None:
            return err("Provider not found.", drf_status.HTTP_404_NOT_FOUND)
        policy = InsurancePolicy.objects.filter(pk=policy_id, provider=provider).first()
        if policy is None:
            return err("Policy not found.", drf_status.HTTP_404_NOT_FOUND)
        coverage = PatientCoverage.objects.create(
            patient=request.user, provider=provider, policy=policy, member_id=member_id
        )
        return Response(
            PatientCoverageSerializer(coverage).data, status=drf_status.HTTP_201_CREATED
        )


class ClaimListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.PATIENT]

    def get(self, request):
        qs = (
            InsuranceClaim.objects.filter(patient=request.user)
            .select_related("policy", "provider")
            .order_by("-created_at")
        )
        return Response(InsuranceClaimSerializer(qs, many=True).data)

    def post(self, request):
        provider_id = request.data.get("provider_id")
        policy_id = request.data.get("policy_id")
        invoice_id = request.data.get("invoice_id")
        amount = request.data.get("amount")
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return err("amount is required and must be an integer.")
        provider = User.objects.filter(pk=provider_id, role=User.Role.INSURANCE).first()
        if provider is None:
            return err("Provider not found.", drf_status.HTTP_404_NOT_FOUND)
        policy = InsurancePolicy.objects.filter(pk=policy_id, provider=provider).first()
        if policy is None:
            return err("Policy not found.", drf_status.HTTP_404_NOT_FOUND)
        claim = InsuranceClaim.objects.create(
            patient=request.user,
            provider=provider,
            policy=policy,
            invoice_id=invoice_id if invoice_id not in ("", None) else None,
            amount=amount,
        )
        return Response(InsuranceClaimSerializer(claim).data, status=drf_status.HTTP_201_CREATED)


class ClaimManageView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.INSURANCE, User.Role.INSURANCE_OFFICER, User.Role.FACILITY_MANAGER]

    def get(self, request):
        qs = (
            InsuranceClaim.objects.filter(provider=provider_account_for(request.user, User.Role.INSURANCE))
            .select_related("policy", "patient")
            .order_by("-created_at")
        )
        return Response(InsuranceClaimSerializer(qs, many=True).data)


class ClaimDecideView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [User.Role.INSURANCE, User.Role.INSURANCE_OFFICER, User.Role.FACILITY_MANAGER]

    def post(self, request, pk):
        insurance_account, denied = require_provider_account(request, User.Role.INSURANCE)
        if denied:
            return denied
        claim = InsuranceClaim.objects.filter(pk=pk, provider=insurance_account).first()
        if claim is None:
            return err("Not found.", drf_status.HTTP_404_NOT_FOUND)
        from operations.models import ClaimAssessment
        if ClaimAssessment.objects.filter(claim=claim).exists():
            return err("This claim must be decided through its benefit assessment workflow.", 409)
        action = request.data.get("action")
        if action == "approve":
            claim.status = InsuranceClaim.Status.APPROVED
        elif action == "reject":
            claim.status = InsuranceClaim.Status.REJECTED
        else:
            return err("action must be approve or reject.")
        claim.save(update_fields=["status"])
        return Response(InsuranceClaimSerializer(claim).data)
