from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from governance.services import audit
from operations.serializers import StrictSerializer
from registry.models import Organization

from workforce.models import PharmacyCustomRole, StaffMembership

from .models import PharmacyRolePolicy


# Page, then actions that require that page. The role sets are permission ceilings.
GROUPS = {
    "overview": ("Overview", {}),
    "inventory": ("Medicine Inventory", {"catalogue_edit": "Add catalogue items and manage formulary links"}),
    "stock-control": ("Batch Stock & Safety", {
        "stock_receive": "Add batches and receive stock",
        "stock_safety": "Record temperatures, quarantine and recall",
        "stock_adjust": "Record other batch adjustments",
        "stock_dispense": "Dispense OTC stock from the batch register",
    }),
    "procurement": ("Procurement", {
        "purchase_edit": "Draft purchase orders",
        "purchase_receive": "Receive approved deliveries",
        "purchase_approve": "Approve and close purchase orders",
    }),
    "stocktake": ("Stocktake", {"stock_count": "Submit physical counts", "stock_approve": "Review stock counts"}),
    "suppliers": ("Suppliers", {"supplier_edit": "Edit suppliers"}),
    "medicine-register": ("Medicine Register", {}),
    "counter": ("New Sale", {"sell": "Record walk-in sales"}),
    "orders": ("Orders & Receipts", {"payment": "Record payment", "receipt_print": "Reprint receipts", "fulfil": "Update order fulfilment"}),
    "shifts": ("Cash Shifts", {"shift_manage": "Open and close cash shifts"}),
    "rx-orders": ("Prescription Queue", {"rx_manage": "Review, prepare and dispense prescriptions"}),
    "safety": ("Safety & Returns", {"safety_manage": "Record returns and safety follow-up"}),
    "transfers": ("Branch Transfers", {"transfer_manage": "Request, dispatch and receive transfers"}),
}
STOCK = {
    "inventory", "catalogue_edit", "stock-control", "stock_receive", "stock_safety", "procurement",
    "purchase_edit", "purchase_receive", "stocktake", "stock_count", "suppliers", "supplier_edit", "medicine-register",
}
SALES = {"counter", "sell", "orders", "payment", "receipt_print", "shifts", "shift_manage"}
DEFAULTS = {
    "cashier": SALES,
    "storekeeper": STOCK,
    "pharmacist": STOCK | SALES | {
        "overview", "stock_adjust", "stock_dispense", "purchase_approve", "stock_approve", "fulfil",
        "rx-orders", "rx_manage", "safety", "safety_manage", "transfers", "transfer_manage",
    },
}


def enabled_permissions(role, pharmacy_id):
    maximum = DEFAULTS.get(role)
    if maximum is None:
        return None
    saved = PharmacyRolePolicy.objects.filter(pharmacy_id=pharmacy_id, role=role).values_list("permissions", flat=True).first()
    return maximum if saved is None else maximum.intersection(saved)


def staff_permissions(user, pharmacy_id):
    custom = StaffMembership.objects.filter(
        user=user, organization__owner_id=pharmacy_id,
        organization__organization_type="pharmacy", organization__active=True,
        organization__status="verified", status=StaffMembership.Status.ACTIVE,
        role=user.role, custom_role__isnull=False,
    ).select_related("custom_role").order_by("-is_primary", "pk").first()
    if custom:
        role = custom.custom_role
        if role.pharmacy_id != pharmacy_id or role.base_role != user.role:
            return set()
        return DEFAULTS.get(user.role, set()).intersection(role.permissions)
    return enabled_permissions(user.role, pharmacy_id)


def permits(user, pharmacy_id, *required):
    enabled = staff_permissions(user, pharmacy_id) if user.role in DEFAULTS else None
    return enabled is None or all(key in enabled for key in required)


def require_pharmacy_permission(user, pharmacy_id, *required):
    if not permits(user, pharmacy_id, *required):
        raise PermissionDenied("Your pharmacy role does not have permission for this action.")


def bound_view(view, page, *, write=None, read=None):
    """Apply a pharmacy policy after DRF establishes identity and existing role permissions."""
    class BoundView(view):
        def initial(self, request, *args, **kwargs):
            super().initial(request, *args, **kwargs)
            if getattr(request.user, "role", None) not in DEFAULTS:
                return
            from .views import provider_account_for
            account = provider_account_for(request.user, "pharmacy")
            if not account:
                raise PermissionDenied("Select an assigned pharmacy workspace.")
            extra = read if request.method in {"GET", "HEAD", "OPTIONS"} else write
            require_pharmacy_permission(request.user, account.pk, page, *([extra] if extra else []))

    return BoundView.as_view()


class RolePolicyInput(StrictSerializer):
    role = serializers.ChoiceField(choices=list(DEFAULTS))
    permissions = serializers.ListField(child=serializers.CharField(max_length=40), max_length=64)

    def validate(self, attrs):
        if set(attrs["permissions"]) - DEFAULTS[attrs["role"]]:
            raise serializers.ValidationError({"permissions": "This role cannot be granted one or more of these permissions."})
        return attrs


class CustomRoleInput(StrictSerializer):
    name = serializers.CharField(max_length=80)
    base_role = serializers.ChoiceField(choices=list(DEFAULTS))
    permissions = serializers.ListField(child=serializers.CharField(max_length=40), max_length=64, default=list)

    def validate_name(self, name):
        if name.casefold() in {"pharmacist", "cashier", "sales cashier", "storekeeper", "pharmacy owner"}:
            raise serializers.ValidationError("Choose a name distinct from the built-in roles.")
        return name

    def validate(self, attrs):
        if set(attrs["permissions"]) - DEFAULTS[attrs["base_role"]]:
            raise serializers.ValidationError({"permissions": "Some permissions exceed this staff role's limits."})
        return attrs


def require_verified_owner(user):
    if user.role != "pharmacy" or not Organization.objects.filter(
        owner=user, organization_type="pharmacy", status="verified", active=True,
    ).exists():
        raise PermissionDenied("Only a verified pharmacy owner can change role permissions.")


def custom_settings(role):
    return {
        "id": role.pk, "name": role.name, "base_role": role.base_role,
        "available": sorted(DEFAULTS[role.base_role]),
        "enabled": sorted(DEFAULTS[role.base_role].intersection(role.permissions)),
    }


class PharmacyRolePolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == "pharmacy":
            return Response({
                "custom_roles": [custom_settings(role) for role in PharmacyCustomRole.objects.filter(pharmacy=request.user)],
                "groups": [{"key": key, "label": label, "actions": actions} for key, (label, actions) in GROUPS.items()],
                "roles": {
                    role: {"available": sorted(default), "enabled": sorted(enabled_permissions(role, request.user.pk))}
                    for role, default in DEFAULTS.items()
                },
            })
        from .views import provider_account_for
        if request.user.role not in DEFAULTS:
            raise PermissionDenied("This account does not use pharmacy staff permissions.")
        account = provider_account_for(request.user, "pharmacy")
        if not account:
            raise PermissionDenied("Select an assigned pharmacy workspace.")
        return Response({"enabled": sorted(staff_permissions(request.user, account.pk))})

    def post(self, request):
        require_verified_owner(request.user)
        payload = CustomRoleInput(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                role = PharmacyCustomRole.objects.create(pharmacy=request.user, **payload.validated_data)
                audit(actor=request.user, action="pharmacy.custom_role.created", resource=role, purpose="operations", request=request)
        except IntegrityError:
            raise serializers.ValidationError({"name": "A role with this name already exists."})
        return Response(custom_settings(role), status=201)

    @transaction.atomic
    def put(self, request):
        require_verified_owner(request.user)
        custom_id = request.data.get("custom_role")
        if custom_id is not None:
            custom_id = serializers.IntegerField(min_value=1).run_validation(custom_id)
            role = get_object_or_404(PharmacyCustomRole.objects.select_for_update(), pk=custom_id, pharmacy=request.user)
            payload = RolePolicyInput(data={"role": role.base_role, "permissions": request.data.get("permissions")})
            payload.is_valid(raise_exception=True)
            role.permissions = sorted(set(payload.validated_data["permissions"]))
            role.save(update_fields=["permissions"])
            audit(actor=request.user, action="pharmacy.custom_role.updated", resource=role, purpose="operations",
                  metadata={"permissions": role.permissions}, request=request)
            return Response(custom_settings(role))
        payload = RolePolicyInput(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        enabled = sorted(set(values["permissions"]))
        policy, _ = PharmacyRolePolicy.objects.update_or_create(
            pharmacy=request.user, role=values["role"], defaults={"permissions": enabled},
        )
        audit(actor=request.user, action="pharmacy.role_permissions.updated", resource=policy, purpose="operations",
              metadata={"role": policy.role, "permissions": enabled}, request=request)
        return Response({"enabled": enabled})
