from enterprise.access import active_role, is_platform_super_admin
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import organization_for_user, user_can_manage_organization
from .models import (
    FacilityRole,
    FacilityRolePermission,
    MembershipRoleAssignment,
    PermissionDefinition,
    StaffMembership,
)


DEFAULT_ROLE_PERMISSIONS = {
    "doctor": {"clinical.view", "clinical.write", "orders.create", "prescriptions.create", "appointments.manage", "inpatient.rounds"},
    "clinical_officer": {"clinical.view", "clinical.write", "orders.create", "prescriptions.create", "appointments.manage", "inpatient.rounds"},
    "dentist": {"clinical.view", "clinical.write", "orders.create", "prescriptions.create", "appointments.manage"},
    "medical_director": {"clinical.view", "clinical.write", "clinical.audit", "staff.view", "credentials.view", "quality.manage", "inpatient.manage"},
    "nurse": {"clinical.view", "triage.write", "nursing.write", "medications.administer", "inpatient.tasks"},
    "midwife": {"clinical.view", "triage.write", "nursing.write", "medications.administer", "maternity.manage"},
    "theatre_nurse": {"clinical.view", "theatre.manage", "medications.administer"},
    "receptionist": {"patients.register", "patients.demographics", "appointments.manage", "queue.manage"},
    "records_officer": {"patients.demographics", "records.manage", "records.export"},
    "cashier": {"billing.view", "billing.create", "payments.collect", "receipts.print"},
    "accountant": {"billing.view", "finance.reconcile", "finance.reports", "refunds.approve"},
    "finance_manager": {"billing.view", "finance.reconcile", "finance.reports", "refunds.approve", "pricing.manage"},
    "pharmacist": {"prescriptions.dispense", "inventory.view", "inventory.adjust", "procurement.view"},
    "storekeeper": {"inventory.view", "inventory.adjust", "procurement.manage"},
    "procurement_officer": {"inventory.view", "procurement.manage", "suppliers.manage"},
    "lab_technician": {"laboratory.view", "laboratory.process", "laboratory.results"},
    "radiologist": {"radiology.view", "radiology.report", "radiology.release"},
    "radiographer": {"radiology.view", "radiology.perform"},
    "facility_manager": {"staff.manage", "departments.manage", "facility.manage", "operations.view", "billing.view", "reports.view"},
    "quality_officer": {"quality.manage", "audit.view", "reports.view"},
    "compliance_officer": {"audit.view", "privacy.manage", "records.export", "security.view"},
    "hr_officer": {"staff.manage", "credentials.view", "scheduling.manage"},
    "it_support": {"technical.manage", "security.view"},
    "insurance_officer": {"insurance.view", "claims.manage", "eligibility.check"},
    "claims_reviewer": {"insurance.view", "claims.review", "claims.decide"},
    "ambulance_dispatcher": {"emergency.dispatch", "patients.demographics"},
    "paramedic": {"emergency.care", "clinical.view", "clinical.write"},
}


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionDefinition
        fields = ["id", "code", "name", "module", "description", "sensitive", "active"]


class FacilityRoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()
    assigned_members = serializers.IntegerField(source="membership_assignments.count", read_only=True)

    class Meta:
        model = FacilityRole
        fields = ["id", "name", "code", "description", "active", "is_system", "permission_codes", "assigned_members", "created_at", "updated_at"]

    def get_permission_codes(self, obj):
        return list(obj.permissions.filter(active=True).values_list("code", flat=True))


class MembershipAssignmentSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    staff_name = serializers.CharField(source="membership.user.display_name", read_only=True)
    staff_email = serializers.CharField(source="membership.user.email", read_only=True)

    class Meta:
        model = MembershipRoleAssignment
        fields = ["id", "membership", "staff_name", "staff_email", "role", "role_name", "valid_from", "valid_until", "active", "created_at"]


class PermissionCatalogueView(APIView):
    def get(self, request):
        return Response(PermissionSerializer(PermissionDefinition.objects.filter(active=True), many=True).data)


class FacilityRoleListCreateView(APIView):
    def _organization(self, request):
        org = organization_for_user(request.user, request.query_params.get("organization_id") or request.data.get("organization_id"))
        if not org or not user_can_manage_organization(request.user, org):
            return None
        return org

    def get(self, request):
        org = self._organization(request)
        if not org:
            return Response({"detail": "A managed organization is required."}, status=403)
        roles = FacilityRole.objects.filter(organization=org).prefetch_related("permissions")
        return Response(FacilityRoleSerializer(roles, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = self._organization(request)
        if not org:
            return Response({"detail": "A managed organization is required."}, status=403)
        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"name": ["Role name is required."]}, status=400)
        code = slugify(request.data.get("code") or name)[:80]
        role, created = FacilityRole.objects.get_or_create(
            organization=org,
            code=code,
            defaults={"name": name, "description": request.data.get("description", ""), "created_by": request.user},
        )
        if not created:
            role.name = name
            role.description = request.data.get("description", role.description)
            role.active = True
            role.save(update_fields=["name", "description", "active", "updated_at"])
        codes = request.data.get("permission_codes", [])
        permissions = PermissionDefinition.objects.filter(code__in=codes, active=True)
        FacilityRolePermission.objects.filter(role=role).exclude(permission__in=permissions).delete()
        for permission in permissions:
            FacilityRolePermission.objects.get_or_create(role=role, permission=permission, defaults={"granted_by": request.user})
        return Response(FacilityRoleSerializer(role).data, status=201 if created else 200)


class FacilityRoleDetailView(APIView):
    def _role(self, request, pk):
        role = FacilityRole.objects.filter(pk=pk).select_related("organization").first()
        if not role or not user_can_manage_organization(request.user, role.organization):
            return None
        return role

    @transaction.atomic
    def patch(self, request, pk):
        role = self._role(request, pk)
        if not role:
            return Response({"detail": "Role not found."}, status=404)
        for field in ["name", "description", "active"]:
            if field in request.data:
                setattr(role, field, request.data[field])
        role.save()
        if "permission_codes" in request.data:
            permissions = PermissionDefinition.objects.filter(code__in=request.data.get("permission_codes", []), active=True)
            FacilityRolePermission.objects.filter(role=role).exclude(permission__in=permissions).delete()
            for permission in permissions:
                FacilityRolePermission.objects.get_or_create(role=role, permission=permission, defaults={"granted_by": request.user})
        return Response(FacilityRoleSerializer(role).data)

    def delete(self, request, pk):
        role = self._role(request, pk)
        if not role:
            return Response({"detail": "Role not found."}, status=404)
        if role.is_system:
            return Response({"detail": "System roles cannot be deleted."}, status=400)
        role.active = False
        role.save(update_fields=["active", "updated_at"])
        return Response(status=204)


class MembershipRoleAssignmentView(APIView):
    def get(self, request):
        org = organization_for_user(request.user, request.query_params.get("organization_id"))
        if not org or not user_can_manage_organization(request.user, org):
            return Response({"detail": "A managed organization is required."}, status=403)
        rows = MembershipRoleAssignment.objects.filter(membership__organization=org).select_related("membership__user", "role")
        return Response(MembershipAssignmentSerializer(rows, many=True).data)

    @transaction.atomic
    def post(self, request):
        membership = StaffMembership.objects.filter(pk=request.data.get("membership")).select_related("organization").first()
        role = FacilityRole.objects.filter(pk=request.data.get("role")).first()
        if not membership or not role or membership.organization_id != role.organization_id:
            return Response({"detail": "Membership and role must belong to the same organization."}, status=400)
        if not user_can_manage_organization(request.user, membership.organization):
            return Response({"detail": "Not permitted."}, status=403)
        row, _ = MembershipRoleAssignment.objects.update_or_create(
            membership=membership,
            role=role,
            defaults={
                "assigned_by": request.user,
                "valid_until": request.data.get("valid_until") or None,
                "active": True,
            },
        )
        return Response(MembershipAssignmentSerializer(row).data, status=201)

    def delete(self, request, pk):
        row = MembershipRoleAssignment.objects.filter(pk=pk).select_related("membership__organization").first()
        if not row or not user_can_manage_organization(request.user, row.membership.organization):
            return Response({"detail": "Assignment not found."}, status=404)
        row.active = False
        row.save(update_fields=["active"])
        return Response(status=204)


def user_permission_codes(user, organization=None):
    """Return effective codes from primary role plus active custom assignments."""
    if not user or not user.is_authenticated:
        return set()
    if is_platform_super_admin(user):
        return {"*"}
    codes = set(DEFAULT_ROLE_PERMISSIONS.get(active_role(user), set()))
    memberships = StaffMembership.objects.filter(user=user, status=StaffMembership.Status.ACTIVE)
    if organization:
        memberships = memberships.filter(organization=organization)
    now = timezone.now()
    custom = PermissionDefinition.objects.filter(
        facility_roles__membership_assignments__membership__in=memberships,
        facility_roles__membership_assignments__active=True,
        facility_roles__membership_assignments__valid_from__lte=now,
        active=True,
    ).filter(
        Q(facility_roles__membership_assignments__valid_until__isnull=True)
        | Q(facility_roles__membership_assignments__valid_until__gt=now)
    )
    codes.update(custom.values_list("code", flat=True))
    return codes
