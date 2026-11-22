from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import DoctorProfile, PatientProfile, ProfileStatus, StaffProfile
from accounts.permissions import IsRole
from accounts.roles import (
    APPOINTMENT_VIEW_ROLES,
    CLINICAL_ROLES,
    FACILITY_MANAGEMENT_ROLES,
    FACILITY_OPERATIONS_ROLES,
    FRONT_DESK_ROLES,
    NURSING_ROLES,
    PROFESSIONAL_ROLES,
    portal_path_for_role,
)
from registry.models import Organization, PractitionerCredential

from .access import organization_for_user, user_can_manage_organization
from .models import (
    Department,
    MedicationAdministration,
    NursingNote,
    PatientVisit,
    StaffInvitation,
    StaffMembership,
    TriageRecord,
)
from .serializers import (
    DepartmentSerializer,
    InvitationAcceptSerializer,
    MedicationAdministrationSerializer,
    NursingNoteSerializer,
    PatientVisitSerializer,
    StaffInvitationSerializer,
    StaffMembershipSerializer,
    TriageRecordSerializer,
)
from .services import assign_queue_number, audit_workforce, create_invitation, emit_workforce_event

User = get_user_model()
MANAGER_ROLES = list(FACILITY_MANAGEMENT_ROLES | {"hospital", "pharmacy", "lab", "insurance", "admin"})
VISIT_ROLES = list(CLINICAL_ROLES | FRONT_DESK_ROLES | FACILITY_MANAGEMENT_ROLES | {"hospital", "admin", "cashier", "lab_technician", "pharmacist"})


def _organization_or_error(request):
    org_id = request.query_params.get("organization") or request.data.get("organization")
    organization = organization_for_user(request.user, org_id)
    if request.user.role == "admin" and org_id:
        organization = Organization.objects.filter(pk=org_id).first()
    return organization


def _verified_clinician_required(request):
    if request.user.role in PROFESSIONAL_ROLES and not request.user.is_verified:
        return Response(
            {"detail": "Your professional licence must be verified before clinical documentation is allowed."},
            status=403,
        )
    return None


class DepartmentListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = MANAGER_ROLES

    def get(self, request):
        organization = _organization_or_error(request)
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        return Response(DepartmentSerializer(organization.departments.all(), many=True).data)

    def post(self, request):
        organization = _organization_or_error(request)
        if not organization or not user_can_manage_organization(request.user, organization):
            return Response({"detail": "You cannot manage this organization."}, status=403)
        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department = serializer.save(organization=organization)
        audit_workforce(request, "workforce.department.created", department)
        return Response(DepartmentSerializer(department).data, status=201)


class StaffListInviteView(APIView):
    permission_classes = [IsRole]
    allowed_roles = MANAGER_ROLES
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        organization = _organization_or_error(request)
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        memberships = organization.staff_memberships.select_related("user", "department")
        role = request.query_params.get("role")
        status_value = request.query_params.get("status")
        if role:
            memberships = memberships.filter(role=role)
        if status_value:
            memberships = memberships.filter(status=status_value)
        invitations = organization.staff_invitations.filter(status="pending").select_related("department")
        return Response(
            {
                "staff": StaffMembershipSerializer(memberships, many=True).data,
                "invitations": StaffInvitationSerializer(invitations, many=True, context={"request": request}).data,
            }
        )

    @transaction.atomic
    def post(self, request):
        organization = _organization_or_error(request)
        if not organization or not user_can_manage_organization(request.user, organization):
            return Response({"detail": "You cannot invite staff to this organization."}, status=403)
        serializer = StaffInvitationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        department = data.get("department")
        if department and department.organization_id != organization.id:
            return Response({"detail": "Department belongs to another organization."}, status=400)
        if User.objects.filter(email__iexact=data["email"]).exists():
            return Response({"detail": "An account with this email already exists. Add an existing-user membership through an administrator."}, status=409)
        invitation = create_invitation(
            organization=organization,
            invited_by=request.user,
            email=data["email"],
            phone=data.get("phone", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            role=data["role"],
            job_title=data.get("job_title", ""),
            employee_number=data.get("employee_number", ""),
            department=department,
        )
        audit_workforce(request, "workforce.invitation.created", invitation, metadata={"role": invitation.role})
        emit_workforce_event(
            "workforce.staff.invited",
            invitation,
            {"organization_id": organization.id, "email": invitation.email, "role": invitation.role},
            request,
        )
        try:
            from django.core.mail import send_mail

            send_mail(
                subject=f"Invitation to join {organization.legal_name} on MyDoctor",
                message=f"You have been invited as {invitation.get_role_display() if hasattr(invitation, 'get_role_display') else invitation.role}. Invitation token: {invitation.token}",
                from_email=None,
                recipient_list=[invitation.email],
                fail_silently=True,
            )
        except Exception:
            pass
        return Response(StaffInvitationSerializer(invitation, context={"request": request}).data, status=201)


class InvitationDetailAcceptView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, token):
        invitation = get_object_or_404(
            StaffInvitation.objects.select_related("organization", "department"), token=token
        )
        if invitation.is_expired and invitation.status == StaffInvitation.Status.PENDING:
            invitation.status = StaffInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
        return Response(StaffInvitationSerializer(invitation, context={"request": request}).data)

    @transaction.atomic
    def post(self, request, token):
        invitation = get_object_or_404(
            StaffInvitation.objects.select_for_update().select_related("organization", "department"), token=token
        )
        if invitation.status != StaffInvitation.Status.PENDING:
            return Response({"detail": "This invitation is no longer available."}, status=409)
        if invitation.is_expired:
            invitation.status = StaffInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
            return Response({"detail": "This invitation has expired."}, status=410)
        if User.objects.filter(email__iexact=invitation.email).exists():
            return Response({"detail": "An account with this email already exists."}, status=409)
        serializer = InvitationAcceptSerializer(
            data=request.data, context={"invitation": invitation}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        professional = invitation.role in PROFESSIONAL_ROLES
        user = User.objects.create_user(
            email=invitation.email,
            password=data["password"],
            first_name=data.get("first_name") or invitation.first_name,
            last_name=data.get("last_name") or invitation.last_name,
            phone=data.get("phone") or invitation.phone,
            role=invitation.role,
            is_verified=not professional,
        )
        if invitation.role == "doctor":
            profile = DoctorProfile.objects.create(
                user=user,
                university=data.get("university", ""),
                year_of_completion=data.get("year_of_completion"),
                cadre=DoctorProfile.Cadre.MEDICAL_OFFICER,
                license_number=data.get("registration_number", ""),
                license_issuer=data.get("license_issuer", ""),
                license_expires_on=data.get("license_expires_on"),
                license_document=data.get("license_document"),
                hospital=invitation.organization.legal_name,
                status=ProfileStatus.PENDING,
            )
        else:
            profile = StaffProfile.objects.create(
                user=user,
                employee_number=invitation.employee_number,
                cadre=invitation.job_title or invitation.role.replace("_", " ").title(),
                university=data.get("university", ""),
                year_of_completion=data.get("year_of_completion"),
                qualification=data.get("qualification", ""),
                registration_number=data.get("registration_number", ""),
                license_issuer=data.get("license_issuer", ""),
                license_expires_on=data.get("license_expires_on"),
                license_document=data.get("license_document"),
                status=ProfileStatus.PENDING if professional else ProfileStatus.VERIFIED,
            )
        StaffMembership.objects.create(
            user=user,
            organization=invitation.organization,
            department=invitation.department,
            role=invitation.role,
            job_title=invitation.job_title,
            employee_number=invitation.employee_number,
            status=StaffMembership.Status.ACTIVE,
            is_primary=True,
            created_by=invitation.invited_by,
        )
        if professional:
            PractitionerCredential.objects.create(
                practitioner=user,
                credential_type=PractitionerCredential.Type.LICENSE,
                identifier=data.get("registration_number", ""),
                issuer=data.get("license_issuer", "") or "Professional regulator",
                title=f"{invitation.role.replace('_', ' ').title()} practising licence",
                expires_on=data.get("license_expires_on"),
                document=data.get("license_document"),
            )
        invitation.status = StaffInvitation.Status.ACCEPTED
        invitation.accepted_by = user
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_by", "accepted_at"])
        try:
            from communication.services import notify

            notify(
                user,
                f"Welcome to {invitation.organization.legal_name}",
                "Your facility workspace is ready." if not professional else "Your workspace is ready. Clinical or professional actions remain limited until your licence is verified.",
                kind="account",
                action_url=portal_path_for_role(user.role),
            )
        except Exception:
            pass
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": {"id": user.id, "email": user.email, "role": user.role, "is_verified": user.is_verified},
                "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
            },
            status=201,
        )


class StaffMembershipStatusView(APIView):
    permission_classes = [IsRole]
    allowed_roles = MANAGER_ROLES

    def post(self, request, pk):
        membership = get_object_or_404(StaffMembership.objects.select_related("organization", "user"), pk=pk)
        if not user_can_manage_organization(request.user, membership.organization):
            return Response({"detail": "You cannot manage this staff membership."}, status=403)
        status_value = request.data.get("status")
        if status_value not in StaffMembership.Status.values:
            return Response({"detail": "Invalid membership status."}, status=400)
        membership.status = status_value
        membership.save(update_fields=["status", "updated_at"])
        # Membership suspension is organization-scoped. Global account suspension
        # is reserved for the platform administrator so work at another facility
        # is not accidentally disabled.
        audit_workforce(request, f"workforce.membership.{status_value}", membership)
        return Response(StaffMembershipSerializer(membership).data)


class PatientSearchCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list(FRONT_DESK_ROLES | FACILITY_MANAGEMENT_ROLES | {"hospital", "admin"})

    def get(self, request):
        search = str(request.query_params.get("search", "")).strip()
        qs = User.objects.filter(role="patient")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
        data = [
            {"id": user.id, "name": user.display_name, "email": user.email, "phone": user.phone, "location": getattr(getattr(user, "patient_profile", None), "location", "")}
            for user in qs.select_related("patient_profile")[:50]
        ]
        return Response(data)

    @transaction.atomic
    def post(self, request):
        required = ["first_name", "last_name", "email", "phone"]
        missing = [field for field in required if not str(request.data.get(field, "")).strip()]
        if missing:
            return Response({field: "This field is required." for field in missing}, status=400)
        email = User.objects.normalize_email(request.data["email"])
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "A user with this email already exists."}, status=409)
        from django.utils.crypto import get_random_string
        temporary_password = get_random_string(20)
        patient = User.objects.create_user(
            email=email,
            password=temporary_password,
            first_name=request.data["first_name"].strip(),
            last_name=request.data["last_name"].strip(),
            phone=request.data["phone"].strip(),
            role="patient",
            is_verified=True,
        )
        PatientProfile.objects.create(
            user=patient,
            location=str(request.data.get("location", "")).strip(),
            address=str(request.data.get("address", "")).strip(),
        )
        audit_workforce(request, "reception.patient.registered", patient, patient=patient)
        return Response(
            {"id": patient.id, "name": patient.display_name, "email": patient.email, "phone": patient.phone, "temporary_password": temporary_password},
            status=201,
        )


class VisitListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = VISIT_ROLES

    def get(self, request):
        organization = _organization_or_error(request)
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        qs = PatientVisit.objects.filter(organization=organization).select_related(
            "patient", "assigned_doctor", "assigned_nurse", "organization"
        )
        from django.db.models import Prefetch
        from services.models import LabOrder

        qs = qs.prefetch_related(Prefetch("lab_orders", queryset=LabOrder.objects.select_related("lab")))
        status_value = request.query_params.get("status")
        date_value = request.query_params.get("date")
        if status_value:
            qs = qs.filter(status=status_value)
        if date_value:
            qs = qs.filter(checked_in_at__date=date_value)
        if request.user.role == "nurse":
            qs = qs.filter(Q(assigned_nurse=request.user) | Q(assigned_nurse__isnull=True))
        elif request.user.role == "doctor":
            qs = qs.filter(Q(assigned_doctor=request.user) | Q(assigned_doctor__isnull=True))
        return Response(PatientVisitSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        organization = _organization_or_error(request)
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = PatientVisitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = serializer.save(
            organization=organization,
            registered_by=request.user,
            status=PatientVisit.Status.WAITING_TRIAGE,
        )
        assign_queue_number(visit)
        audit_workforce(request, "visit.checked_in", visit, patient=visit.patient)
        emit_workforce_event(
            "visit.checked_in",
            visit,
            {"visit_number": visit.visit_number, "patient_id": visit.patient_id, "organization_id": organization.id},
            request,
            patient=visit.patient,
        )
        try:
            from communication.services import notify

            notify(
                visit.patient,
                "Check-in complete",
                f"You are checked in at {organization.legal_name}. Queue number: {visit.queue_number}.",
                kind="visit",
                action_url="/patient/appointments",
            )
        except Exception:
            pass
        return Response(PatientVisitSerializer(visit).data, status=201)


class VisitActionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = VISIT_ROLES

    assignment_roles = FRONT_DESK_ROLES | FACILITY_MANAGEMENT_ROLES | {"admin", "hospital"}

    def eligible_assignees(self, visit):
        from operations.access import organizations
        from registry.models import PractitionerRole

        staff = StaffMembership.objects.filter(organization=visit.organization, status="active").values("user_id")
        practitioners = PractitionerRole.objects.filter(organization=visit.organization, active=True).values("practitioner_id")
        candidates = User.objects.filter(
            Q(pk__in=staff) | Q(pk__in=practitioners),
            is_active=True, is_verified=True, role__in=CLINICAL_ROLES,
        ).order_by("first_name", "last_name", "pk")
        return [user for user in candidates if organizations(user).filter(pk=visit.organization_id).exists()]

    def get(self, request, pk):
        if request.user.role not in self.assignment_roles:
            return Response({"detail": "This role cannot assign care-team members."}, status=403)
        visit = get_object_or_404(PatientVisit.objects.select_related("organization"), pk=pk)
        if request.user.role != "admin" and organization_for_user(request.user, visit.organization_id) is None:
            return Response({"detail": "This visit is outside your organization."}, status=403)
        return Response([
            {"id": user.pk, "name": user.display_name, "role": user.role}
            for user in self.eligible_assignees(visit)
        ])

    @transaction.atomic
    def post(self, request, pk):
        visit = get_object_or_404(PatientVisit.objects.select_for_update().select_related("organization", "patient"), pk=pk)
        organization = organization_for_user(request.user, visit.organization_id)
        if request.user.role != "admin" and organization is None:
            return Response({"detail": "This visit is outside your organization."}, status=403)
        if request.data.get("action") == "lab_arrival":
            from services.models import LabOrder

            if request.user.role not in FRONT_DESK_ROLES | FACILITY_MANAGEMENT_ROLES | {"hospital", "admin"}:
                return Response({"detail": "This role cannot record a front-desk handoff."}, status=403)
            order = get_object_or_404(LabOrder.objects.select_for_update(), pk=request.data.get("order"), visit=visit)
            if order.arrived_at is None:
                if visit.status in {PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED} or order.status not in {
                    LabOrder.Status.BOOKED, LabOrder.Status.READY_FOR_COLLECTION,
                }:
                    return Response({"detail": "This order is not awaiting check-in."}, status=409)
                order.arrived_at = timezone.now()
                order.save(update_fields=["arrived_at", "updated_at"])
                audit_workforce(request, "visit.laboratory.arrived", order, patient=visit.patient)
            return Response(PatientVisitSerializer(visit).data)
        if request.data.get("action") == "resume_after_lab":
            if request.user.role != "doctor" or not request.user.is_verified or visit.assigned_doctor_id != request.user.pk:
                return Response({"detail": "Only the assigned doctor can resume this consultation."}, status=403)
            if visit.status == PatientVisit.Status.IN_CONSULTATION:
                return Response(PatientVisitSerializer(visit).data)
            if visit.status != PatientVisit.Status.LABORATORY or not visit.lab_orders.filter(result_released=True).exists():
                return Response({"detail": "A released laboratory result is required."}, status=409)
            visit.status = PatientVisit.Status.IN_CONSULTATION
            visit.save(update_fields=["status", "updated_at"])
            audit_workforce(request, "visit.consultation_resumed_after_lab", visit, patient=visit.patient)
            return Response(PatientVisitSerializer(visit).data)
        assignment_only = request.data.get("action") == "assign_care_team"
        status_value = visit.status if assignment_only else request.data.get("status")
        if assignment_only and request.user.role not in self.assignment_roles:
            return Response({"detail": "This role cannot assign care-team members."}, status=403)
        if assignment_only and visit.status in {PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED}:
            return Response({"detail": "A closed visit cannot be reassigned."}, status=409)
        if status_value not in PatientVisit.Status.values:
            return Response({"detail": "Invalid visit status."}, status=400)
        allowed_statuses = {
            "receptionist": {
                PatientVisit.Status.REGISTERED,
                PatientVisit.Status.WAITING_TRIAGE,
                PatientVisit.Status.CANCELLED,
            },
            "records_officer": {
                PatientVisit.Status.REGISTERED,
                PatientVisit.Status.WAITING_TRIAGE,
                PatientVisit.Status.CANCELLED,
            },
            "nurse": {
                PatientVisit.Status.TRIAGED,
                PatientVisit.Status.WAITING_CLINICIAN,
                PatientVisit.Status.LABORATORY,
                PatientVisit.Status.PHARMACY,
                PatientVisit.Status.BILLING,
                PatientVisit.Status.COMPLETED,
            },
            "doctor": {
                PatientVisit.Status.IN_CONSULTATION,
                PatientVisit.Status.LABORATORY,
                PatientVisit.Status.PHARMACY,
                PatientVisit.Status.BILLING,
                PatientVisit.Status.COMPLETED,
            },
            "lab_technician": {
                PatientVisit.Status.LABORATORY,
                PatientVisit.Status.WAITING_CLINICIAN,
                PatientVisit.Status.BILLING,
            },
            "pharmacist": {
                PatientVisit.Status.PHARMACY,
                PatientVisit.Status.BILLING,
                PatientVisit.Status.COMPLETED,
            },
            "cashier": {PatientVisit.Status.BILLING, PatientVisit.Status.COMPLETED},
        }
        if not assignment_only and request.user.role not in {"admin", "hospital", "facility_manager"}:
            if status_value not in allowed_statuses.get(request.user.role, set()):
                return Response(
                    {"detail": "This visit transition is not permitted for your role."},
                    status=403,
                )
        if ({"assigned_doctor", "assigned_nurse"} & set(request.data.keys())) and request.user.role not in self.assignment_roles:
            return Response({"detail": "Your role cannot assign care-team members."}, status=403)
        eligible = None
        for role in ("doctor", "nurse"):
            field = f"assigned_{role}"
            if field not in request.data:
                continue
            selection = request.data[field]
            if selection:
                if eligible is None:
                    eligible = self.eligible_assignees(visit)
                if not any(user.role == role and str(user.pk) == str(selection) for user in eligible):
                    return Response({"detail": f"Select a verified {role} at this facility."}, status=400)
            setattr(visit, f"{field}_id", selection or None)
        visit.status = status_value
        if status_value == PatientVisit.Status.COMPLETED:
            visit.checked_out_at = timezone.now()
        visit.save()
        audit_workforce(request, "visit.care_team_assigned" if assignment_only else f"visit.{status_value}", visit, patient=visit.patient)
        return Response(PatientVisitSerializer(visit).data)


class TriageListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list(NURSING_ROLES | {"admin"})

    def get(self, request):
        organization = _organization_or_error(request)
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        qs = TriageRecord.objects.filter(visit__organization=organization).select_related("visit__patient", "nurse")
        return Response(TriageRecordSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        denied = _verified_clinician_required(request)
        if denied:
            return denied
        visit = get_object_or_404(PatientVisit, pk=request.data.get("visit"))
        if request.user.role != "admin" and organization_for_user(request.user, visit.organization_id) is None:
            return Response({"detail": "This visit is outside your organization."}, status=403)
        serializer = TriageRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        triage, created = TriageRecord.objects.update_or_create(
            visit=visit,
            defaults={**serializer.validated_data, "nurse": request.user},
        )
        visit.assigned_nurse = request.user if request.user.role == "nurse" else visit.assigned_nurse
        visit.status = PatientVisit.Status.WAITING_CLINICIAN
        visit.priority = PatientVisit.Priority.EMERGENCY if triage.level == TriageRecord.Level.RED else (
            PatientVisit.Priority.URGENT if triage.level in {TriageRecord.Level.ORANGE, TriageRecord.Level.YELLOW} else PatientVisit.Priority.ROUTINE
        )
        visit.save(update_fields=["assigned_nurse", "status", "priority", "updated_at"])
        audit_workforce(request, "triage.recorded", triage, patient=visit.patient)
        emit_workforce_event(
            "triage.recorded",
            triage,
            {"visit_number": visit.visit_number, "level": triage.level, "patient_id": visit.patient_id},
            request,
            patient=visit.patient,
        )
        return Response(TriageRecordSerializer(triage).data, status=201 if created else 200)


class NursingNoteListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list(NURSING_ROLES | {"admin"})

    def get(self, request):
        visit_id = request.query_params.get("visit")
        qs = NursingNote.objects.select_related("visit__patient", "nurse")
        if visit_id:
            qs = qs.filter(visit_id=visit_id)
        organization = _organization_or_error(request)
        if organization:
            qs = qs.filter(visit__organization=organization)
        elif request.user.role != "admin" or request.query_params.get("organization"):
            return Response({"detail": "No organization is in scope."}, status=403)
        if request.query_params.get("note_type"):
            qs = qs.filter(note_type=request.query_params["note_type"])
        return Response(NursingNoteSerializer(qs, many=True).data)

    def post(self, request):
        denied = _verified_clinician_required(request)
        if denied:
            return denied
        visit = get_object_or_404(PatientVisit, pk=request.data.get("visit"))
        if request.user.role != "admin" and organization_for_user(request.user, visit.organization_id) is None:
            return Response({"detail": "This visit is outside your organization."}, status=403)
        serializer = NursingNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(nurse=request.user)
        audit_workforce(request, "nursing.note.created", note, patient=visit.patient)
        return Response(NursingNoteSerializer(note).data, status=201)


class MedicationAdministrationListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list(NURSING_ROLES | {"admin"})

    def get(self, request):
        visit_id = request.query_params.get("visit")
        qs = MedicationAdministration.objects.select_related("visit__patient", "nurse")
        if visit_id:
            qs = qs.filter(visit_id=visit_id)
        organization = _organization_or_error(request)
        if organization:
            qs = qs.filter(visit__organization=organization)
        return Response(MedicationAdministrationSerializer(qs, many=True).data)

    def post(self, request):
        denied = _verified_clinician_required(request)
        if denied:
            return denied
        visit = get_object_or_404(PatientVisit, pk=request.data.get("visit"))
        if request.user.role != "admin" and organization_for_user(request.user, visit.organization_id) is None:
            return Response({"detail": "This visit is outside your organization."}, status=403)
        serializer = MedicationAdministrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        administration = serializer.save(nurse=request.user)
        audit_workforce(request, "medication.administered", administration, patient=visit.patient)
        return Response(MedicationAdministrationSerializer(administration).data, status=201)


class OperationsSummaryView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list(FACILITY_OPERATIONS_ROLES | {"admin"})

    def get(self, request):
        organization = _organization_or_error(request)
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        today = timezone.localdate()
        visits = PatientVisit.objects.filter(organization=organization, checked_in_at__date=today)
        return Response(
            {
                "organization": {"id": organization.id, "name": organization.legal_name},
                "today_visits": visits.count(),
                "waiting_triage": visits.filter(status=PatientVisit.Status.WAITING_TRIAGE).count(),
                "waiting_clinician": visits.filter(status=PatientVisit.Status.WAITING_CLINICIAN).count(),
                "in_consultation": visits.filter(status=PatientVisit.Status.IN_CONSULTATION).count(),
                "billing": visits.filter(status=PatientVisit.Status.BILLING).count(),
                "completed": visits.filter(status=PatientVisit.Status.COMPLETED).count(),
                "active_staff": organization.staff_memberships.filter(status=StaffMembership.Status.ACTIVE).count(),
                "staff_by_role": list(
                    organization.staff_memberships.filter(status=StaffMembership.Status.ACTIVE)
                    .values("role")
                    .annotate(count=Count("id"))
                    .order_by("role")
                ),
            }
        )
