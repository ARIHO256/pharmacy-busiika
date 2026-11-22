from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    DoctorProfile,
    PatientProfile,
    ProfileStatus,
    ProviderProfile,
    StaffProfile,
    User,
)
from .permissions import IsRole
from .roles import (
    ORGANIZATION_ACCOUNT_ROLES,
    PROFESSIONAL_ROLES,
    STAFF_ROLES,
    portal_path_for_role,
)
from .serializers import (
    DoctorProfileSerializer,
    PatientProfileSerializer,
    ProviderProfileSerializer,
    PublicDoctorDetailSerializer,
    PublicDoctorSerializer,
    RegisterSerializer,
    StaffProfileSerializer,
    UserSerializer,
)

PROVIDER_ROLES = list(ORGANIZATION_ACCOUNT_ROLES)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/"""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class RegisterView(APIView):
    """Create a patient, doctor or organization operator account."""

    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            first_field = next(iter(errors), None)
            first_value = errors.get(first_field) if first_field else None
            if isinstance(first_value, (list, tuple)) and first_value:
                detail = str(first_value[0])
            elif isinstance(first_value, dict):
                nested = next(iter(first_value.values()), ["Invalid registration data."])
                detail = str(nested[0] if isinstance(nested, (list, tuple)) else nested)
            else:
                detail = "Invalid registration data."
            return Response(
                {"detail": detail, "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        try:
            from communication.services import notify

            notify(
                user,
                "Welcome to MyDoctor",
                (
                    "Your account is ready. You can start booking care immediately."
                    if user.role == User.Role.PATIENT
                    else "Your profile was submitted for verification. Public listing and restricted actions remain disabled until approval."
                ),
                kind="account",
                action_url=portal_path_for_role(user.role),
            )
        except Exception:
            pass
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


def _profile_for_user(user):
    if user.role == User.Role.PATIENT:
        profile, _ = PatientProfile.objects.get_or_create(user=user)
        return profile, PatientProfileSerializer
    if user.role == User.Role.DOCTOR:
        profile, _ = DoctorProfile.objects.get_or_create(user=user)
        return profile, DoctorProfileSerializer
    if user.role in PROVIDER_ROLES:
        type_map = {
            User.Role.HOSPITAL: ProviderProfile.OrganizationType.HOSPITAL,
            User.Role.PHARMACY: ProviderProfile.OrganizationType.PHARMACY,
            User.Role.LAB: ProviderProfile.OrganizationType.LABORATORY,
            User.Role.INSURANCE: ProviderProfile.OrganizationType.INSURER,
        }
        profile, _ = ProviderProfile.objects.get_or_create(
            user=user,
            defaults={"organization_type": type_map[user.role]},
        )
        return profile, ProviderProfileSerializer
    if user.role in STAFF_ROLES:
        profile, _ = StaffProfile.objects.get_or_create(user=user)
        return profile, StaffProfileSerializer
    return None, None


class MyProfileView(APIView):
    """GET/PATCH profile matching the authenticated primary portal role."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        profile, serializer_class = _profile_for_user(request.user)
        if profile is None:
            return Response(
                {"detail": "No profile for this role."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer_class(profile, context={"request": request}).data)

    @transaction.atomic
    def patch(self, request):
        profile, serializer_class = _profile_for_user(request.user)
        if profile is None:
            return Response(
                {"detail": "No profile for this role."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = serializer_class(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        if request.user.role == User.Role.DOCTOR:
            credential_fields = {
                "license_number",
                "license_issuer",
                "license_expires_on",
                "license_document",
            }
            if credential_fields.intersection(request.data.keys()):
                from registry.models import PractitionerCredential

                credential = (
                    PractitionerCredential.objects.filter(
                        practitioner=request.user,
                        credential_type=PractitionerCredential.Type.LICENSE,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if credential is None:
                    credential = PractitionerCredential(practitioner=request.user)
                credential.credential_type = PractitionerCredential.Type.LICENSE
                credential.identifier = profile.license_number
                credential.issuer = profile.license_issuer or "Professional regulator"
                credential.title = "Practising licence"
                credential.expires_on = profile.license_expires_on
                if profile.license_document:
                    credential.document = profile.license_document
                credential.status = PractitionerCredential.Status.PENDING
                credential.verified_by = None
                credential.verified_at = None
                credential.save()
                profile.status = ProfileStatus.PENDING
                profile.verification_notes = "Credential details changed and require review."
                profile.save(update_fields=["status", "verification_notes"])
                if request.user.is_verified:
                    request.user.is_verified = False
                    request.user.save(update_fields=["is_verified"])
        elif request.user.role in (PROFESSIONAL_ROLES - {User.Role.DOCTOR}):
            credential_fields = {
                "registration_number",
                "license_issuer",
                "license_expires_on",
                "license_document",
            }
            if credential_fields.intersection(request.data.keys()):
                from registry.models import PractitionerCredential

                credential = (
                    PractitionerCredential.objects.filter(
                        practitioner=request.user,
                        credential_type=PractitionerCredential.Type.LICENSE,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if credential is None:
                    credential = PractitionerCredential(
                        practitioner=request.user,
                        credential_type=PractitionerCredential.Type.LICENSE,
                    )
                credential.identifier = profile.registration_number
                credential.issuer = profile.license_issuer or "Professional regulator"
                credential.title = f"{request.user.get_role_display()} practising licence"
                credential.expires_on = profile.license_expires_on
                if profile.license_document:
                    credential.document = profile.license_document
                credential.status = PractitionerCredential.Status.PENDING
                credential.verified_by = None
                credential.verified_at = None
                credential.save()
                profile.status = ProfileStatus.PENDING
                profile.save(update_fields=["status"])
                if request.user.is_verified:
                    request.user.is_verified = False
                    request.user.save(update_fields=["is_verified"])
        if request.user.role in PROVIDER_ROLES:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            from registry.services import sync_provider_organization

            credential_changed = bool(
                {"organization_type", "license_number", "license_document"}.intersection(request.data.keys())
            )
            if credential_changed:
                profile.status = ProfileStatus.PENDING
                profile.verification_notes = (
                    "Organization licence details changed and require review."
                )
                profile.save(update_fields=["status", "verification_notes"])
                if request.user.is_verified:
                    request.user.is_verified = False
                    request.user.save(update_fields=["is_verified"])
            try:
                sync_provider_organization(
                    request.user,
                    profile,
                    authoritative_status=credential_changed,
                )
            except ValueError as exc:
                raise DRFValidationError({"detail": str(exc)}) from exc
        return Response(serializer_class(profile, context={"request": request}).data)


class DoctorVerifyUploadView(APIView):
    """Doctor submits or replaces professional credential evidence."""

    permission_classes = [IsRole]
    allowed_roles = [User.Role.DOCTOR]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        profile, _ = DoctorProfile.objects.get_or_create(user=request.user)
        submitted_number = str(
            request.data.get("license_number", profile.license_number) or ""
        ).strip()
        submitted_document = request.FILES.get("license_document") or profile.license_document
        if not submitted_number:
            return Response({"detail": "license_number is required."}, status=400)
        if not submitted_document:
            return Response({"detail": "license_document is required."}, status=400)
        serializer = DoctorProfileSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()

        profile.status = ProfileStatus.PENDING
        profile.verification_notes = "Credential submitted and awaiting administrator review."
        profile.save(update_fields=["status", "verification_notes"])
        if request.user.is_verified:
            request.user.is_verified = False
            request.user.save(update_fields=["is_verified"])

        from registry.models import PractitionerCredential

        credential = (
            PractitionerCredential.objects.filter(
                practitioner=request.user,
                credential_type=PractitionerCredential.Type.LICENSE,
            )
            .order_by("-created_at")
            .first()
        )
        if credential is None:
            credential = PractitionerCredential(
                practitioner=request.user,
                credential_type=PractitionerCredential.Type.LICENSE,
            )
        credential.identifier = profile.license_number.strip()
        credential.issuer = profile.license_issuer.strip() or "Professional regulator"
        credential.title = "Practising licence"
        credential.expires_on = profile.license_expires_on
        credential.document = profile.license_document
        credential.status = PractitionerCredential.Status.PENDING
        credential.verified_by = None
        credential.verified_at = None
        credential.save()
        try:
            from interoperability.services import emit_event

            emit_event(
                "professional.credential.submitted",
                credential,
                {"practitioner_id": request.user.id, "identifier": credential.identifier},
                actor=request.user,
                request=request,
            )
        except Exception:
            pass
        return Response(
            DoctorProfileSerializer(profile, context={"request": request}).data
        )


def _verified_doctors_qs():
    return User.objects.filter(
        role=User.Role.DOCTOR,
        is_active=True,
        is_verified=True,
        doctor_profile__status=ProfileStatus.VERIFIED,
    ).select_related("doctor_profile")


def _public_doctor_payload(user, detail=False):
    profile = user.doctor_profile
    data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "cadre": profile.get_cadre_display() or profile.cadre,
        "specialization": profile.specialization,
        "hospital": profile.hospital,
        "experience_years": profile.experience_years,
        "fees": profile.fees,
        "bio": profile.bio,
        "average_rating": profile.average_rating,
    }
    if detail:
        data["status"] = profile.status
    return data


class DoctorListView(APIView):
    """Public list contains verified and active doctors only."""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = _verified_doctors_qs()
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(doctor_profile__specialization__icontains=search)
                | Q(doctor_profile__cadre__icontains=search)
                | Q(doctor_profile__hospital__icontains=search)
            )
        min_fee = request.query_params.get("min_fee")
        max_fee = request.query_params.get("max_fee")
        if min_fee is not None:
            try:
                qs = qs.filter(doctor_profile__fees__gte=int(min_fee))
            except ValueError:
                return Response({"detail": "min_fee must be an integer."}, status=400)
        if max_fee is not None:
            try:
                qs = qs.filter(doctor_profile__fees__lte=int(max_fee))
            except ValueError:
                return Response({"detail": "max_fee must be an integer."}, status=400)
        serializer = PublicDoctorSerializer([_public_doctor_payload(u) for u in qs], many=True)
        return Response(serializer.data)


class DoctorDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            user = _verified_doctors_qs().get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Doctor not found."}, status=404)
        serializer = PublicDoctorDetailSerializer(_public_doctor_payload(user, detail=True))
        return Response(serializer.data)
