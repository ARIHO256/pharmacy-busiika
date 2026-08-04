from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import IsRole, request_role
from .models import (
    DoctorProfile,
    PatientProfile,
    PatientRelationship,
    ProfileStatus,
    ProviderProfile,
    StaffProfile,
    User,
)
from .roles import (
    BOOKABLE_PROVIDER_ROLES,
    ORGANIZATION_ACCOUNT_ROLES,
    PROFESSIONAL_ROLES,
    STAFF_ROLES,
    portal_path_for_role,
)
from .professionals import public_professional_payload
from .serializers import (
    DependentCreateSerializer,
    DoctorProfileSerializer,
    PatientProfileSerializer,
    PatientRelationshipSerializer,
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
        if request_role(request) == User.Role.DOCTOR:
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
        elif request_role(request) in (PROFESSIONAL_ROLES - {User.Role.DOCTOR}):
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
        if request_role(request) in PROVIDER_ROLES:
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
    """Return verified, active and publicly bookable clinical professionals.

    The legacy endpoint name is preserved for frontend compatibility, while the
    payload now clearly exposes each provider's actual cadre and role.
    """
    return (
        User.objects.filter(
            role__in=BOOKABLE_PROVIDER_ROLES,
            is_active=True,
            is_verified=True,
        )
        .filter(
            Q(role=User.Role.DOCTOR, doctor_profile__status=ProfileStatus.VERIFIED)
            | Q(
                staff_profile__status=ProfileStatus.VERIFIED,
                staff_profile__offers_appointments=True,
            )
        )
        .select_related("doctor_profile", "staff_profile")
        .distinct()
    )


def _public_doctor_payload(user, detail=False):
    return public_professional_payload(user, detail=detail)


class DoctorListView(APIView):
    """Public directory contains verified and active bookable professionals only."""

    permission_classes = [AllowAny]

    def get(self, request):
        providers = [_public_doctor_payload(user) for user in _verified_doctors_qs()]
        search = str(request.query_params.get("search", "")).strip().lower()
        if search:
            providers = [
                row for row in providers
                if search in " ".join(
                    str(row.get(key, "")) for key in
                    ("first_name", "last_name", "cadre", "role_label", "specialization", "hospital")
                ).lower()
            ]
        try:
            min_fee = int(request.query_params["min_fee"]) if "min_fee" in request.query_params else None
            max_fee = int(request.query_params["max_fee"]) if "max_fee" in request.query_params else None
        except (TypeError, ValueError):
            return Response({"detail": "Fee filters must be integers."}, status=400)
        if min_fee is not None:
            providers = [row for row in providers if row["fees"] >= min_fee]
        if max_fee is not None:
            providers = [row for row in providers if row["fees"] <= max_fee]
        role_filter = str(request.query_params.get("role", "")).strip()
        if role_filter:
            providers = [row for row in providers if row["role"] == role_filter]
        providers.sort(key=lambda row: (-float(row["average_rating"]), row["last_name"], row["first_name"]))
        serializer = PublicDoctorSerializer(providers, many=True)
        return Response(serializer.data)


class DoctorDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            user = _verified_doctors_qs().get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Healthcare professional not found."}, status=404)
        serializer = PublicDoctorDetailSerializer(_public_doctor_payload(user, detail=True))
        return Response(serializer.data)


class DependentListCreateView(APIView):
    """Create and manage dependent patient identities without sharing credentials."""

    permission_classes = [IsRole]
    allowed_roles = ["patient", "admin"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        if request_role(request) == User.Role.ADMIN:
            rows = PatientRelationship.objects.select_related(
                "caregiver", "patient", "patient__patient_profile"
            ).all()
            status_filter = request.query_params.get("status")
            if status_filter:
                rows = rows.filter(status=status_filter)
        else:
            rows = PatientRelationship.objects.select_related(
                "caregiver", "patient", "patient__patient_profile"
            ).filter(caregiver=request.user)
        return Response(PatientRelationshipSerializer(rows, many=True, context={"request": request}).data)

    def post(self, request):
        if request_role(request) != User.Role.PATIENT:
            return Response({"detail": "Only patient accounts can create dependents."}, status=403)
        serializer = DependentCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        relationship = serializer.save()
        try:
            from governance.services import audit
            audit(
                actor=request.user, patient=relationship.patient, action="dependent.created",
                resource=relationship, purpose="caregiver_management", decision="allow", request=request,
                metadata={"relationship": relationship.relationship, "status": relationship.status},
            )
        except Exception:
            pass
        return Response(
            PatientRelationshipSerializer(relationship, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DependentDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "admin"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_object(self, request, pk):
        rows = PatientRelationship.objects.select_related(
            "caregiver", "patient", "patient__patient_profile"
        )
        if request_role(request) != User.Role.ADMIN:
            rows = rows.filter(caregiver=request.user)
        return rows.filter(pk=pk).first()

    def patch(self, request, pk):
        relationship = self.get_object(request, pk)
        if relationship is None:
            return Response({"detail": "Dependent relationship not found."}, status=404)
        profile = relationship.patient.patient_profile
        patient_fields = {
            "first_name", "last_name", "dob", "gender", "blood_group", "allergies",
            "medical_history", "emergency_contact", "location", "address",
        }
        relation_fields = {
            "relationship", "can_book", "can_view_records", "can_manage_billing",
            "can_receive_notifications", "notes", "expires_at",
        }
        with transaction.atomic():
            changed_user = []
            for field in {"first_name", "last_name"}:
                if field in request.data:
                    setattr(relationship.patient, field, str(request.data[field]).strip())
                    changed_user.append(field)
            if changed_user:
                relationship.patient.save(update_fields=changed_user)
            profile_payload = {key: request.data[key] for key in patient_fields if key in request.data and key not in {"first_name", "last_name"}}
            if profile_payload:
                profile_serializer = PatientProfileSerializer(profile, data=profile_payload, partial=True)
                profile_serializer.is_valid(raise_exception=True)
                profile_serializer.save()
            for field in relation_fields:
                if field in request.data:
                    setattr(relationship, field, request.data[field])
            if "authority_document" in request.FILES:
                relationship.authority_document = request.FILES["authority_document"]
            relationship.save()
        return Response(PatientRelationshipSerializer(relationship, context={"request": request}).data)

    def delete(self, request, pk):
        relationship = self.get_object(request, pk)
        if relationship is None:
            return Response({"detail": "Dependent relationship not found."}, status=404)
        relationship.status = PatientRelationship.Status.REVOKED
        relationship.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Caregiver access revoked."})


class PatientRelationshipActionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "admin"]

    def post(self, request, pk):
        from django.utils import timezone

        relationship = PatientRelationship.objects.select_related("caregiver", "patient").filter(pk=pk).first()
        if relationship is None:
            return Response({"detail": "Relationship not found."}, status=404)
        action = str(request.data.get("action", "")).lower()
        if request_role(request) == User.Role.ADMIN:
            allowed = {"approve", "suspend", "reactivate", "revoke"}
            if action not in allowed:
                return Response({"detail": "action must be approve, suspend, reactivate or revoke."}, status=400)
            relationship.status = {
                "approve": PatientRelationship.Status.ACTIVE,
                "reactivate": PatientRelationship.Status.ACTIVE,
                "suspend": PatientRelationship.Status.SUSPENDED,
                "revoke": PatientRelationship.Status.REVOKED,
            }[action]
            relationship.verified_by = request.user
            relationship.verified_at = timezone.now()
        elif request.user.pk == relationship.patient_id and action == "revoke":
            relationship.status = PatientRelationship.Status.REVOKED
        else:
            return Response({"detail": "You cannot perform this relationship action."}, status=403)
        relationship.notes = str(request.data.get("reason", relationship.notes or ""))
        relationship.save()
        return Response(PatientRelationshipSerializer(relationship, context={"request": request}).data)


class PatientRelationshipDocumentView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "admin"]

    def get(self, request, pk):
        from django.http import FileResponse

        relationship = PatientRelationship.objects.filter(pk=pk).first()
        if relationship is None or not relationship.authority_document:
            return Response({"detail": "Authority document not found."}, status=404)
        if request_role(request) != User.Role.ADMIN and request.user.pk not in {relationship.caregiver_id, relationship.patient_id}:
            return Response({"detail": "You are not allowed to view this document."}, status=403)
        response = FileResponse(relationship.authority_document.open("rb"), as_attachment=False)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class SecureTokenView(APIView):
    """Password sign-in with lockout controls and optional email one-time-code MFA."""

    permission_classes = [AllowAny]

    def post(self, request):
        from django.conf import settings
        from .models import OneTimeToken, SecurityEvent
        from .security import account_login, issue_jwt, issue_token, record_security_event, send_security_email

        user = account_login(request, request.data.get("email", ""), request.data.get("password", ""))
        if user.mfa_enabled:
            challenge, code = issue_token(
                user,
                OneTimeToken.Purpose.MFA_LOGIN,
                request=request,
                minutes=settings.MFA_CODE_MINUTES,
                numeric=True,
            )
            send_security_email(
                user,
                "Your MyDoctor sign-in code",
                f"Your MyDoctor sign-in code is {code}. It expires in {settings.MFA_CODE_MINUTES} minutes. If this was not you, reset your password immediately.",
            )
            record_security_event(request, SecurityEvent.Type.MFA_CHALLENGE, user)
            return Response(
                {"mfa_required": True, "challenge_id": str(challenge.public_id), "delivery": "email"},
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(issue_jwt(user))


class MfaVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from .models import OneTimeToken
        from .security import consume_token, issue_jwt

        challenge_id = request.data.get("challenge_id")
        code = request.data.get("code")
        if not challenge_id or not code:
            return Response({"detail": "challenge_id and code are required."}, status=400)
        user = consume_token(challenge_id, code, OneTimeToken.Purpose.MFA_LOGIN)
        return Response(issue_jwt(user))


class RequestEmailVerificationView(APIView):
    def post(self, request):
        from django.conf import settings
        from .models import OneTimeToken
        from .security import issue_token, send_security_email

        if request.user.email_verified_at:
            return Response({"detail": "Email is already verified."})
        token, raw = issue_token(
            request.user,
            OneTimeToken.Purpose.EMAIL_VERIFICATION,
            request=request,
            minutes=settings.EMAIL_VERIFICATION_MINUTES,
        )
        url = f"{settings.FRONTEND_URL}/verify-email/{token.public_id}/{raw}"
        send_security_email(request.user, "Verify your MyDoctor email", f"Verify your email by opening this link:\n\n{url}")
        return Response({"detail": "Verification email sent."})


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.utils import timezone
        from .models import OneTimeToken, SecurityEvent
        from .security import consume_token, record_security_event

        user = consume_token(
            request.data.get("token_id"),
            request.data.get("token"),
            OneTimeToken.Purpose.EMAIL_VERIFICATION,
        )
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        record_security_event(request, SecurityEvent.Type.EMAIL_VERIFIED, user)
        return Response({"detail": "Email verified successfully."})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.conf import settings
        from .models import OneTimeToken, User
        from .security import issue_token, send_security_email

        email = User.objects.normalize_email(request.data.get("email", ""))
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            token, raw = issue_token(
                user,
                OneTimeToken.Purpose.PASSWORD_RESET,
                request=request,
                minutes=settings.PASSWORD_RESET_MINUTES,
            )
            url = f"{settings.FRONTEND_URL}/reset-password/{token.public_id}/{raw}"
            send_security_email(user, "Reset your MyDoctor password", f"Reset your password using this link:\n\n{url}\n\nThe link expires in {settings.PASSWORD_RESET_MINUTES} minutes.")
        return Response({"detail": "If that account exists, a password-reset message has been sent."})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.utils import timezone
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        from .models import OneTimeToken, SecurityEvent
        from .security import consume_token, record_security_event

        password = request.data.get("password", "")
        user = consume_token(request.data.get("token_id"), request.data.get("token"), OneTimeToken.Purpose.PASSWORD_RESET)
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=400)
        user.set_password(password)
        user.last_password_change_at = timezone.now()
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["password", "last_password_change_at", "failed_login_attempts", "locked_until"])
        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)
        record_security_event(request, SecurityEvent.Type.PASSWORD_RESET, user)
        return Response({"detail": "Password reset successfully. Sign in with your new password."})


class ChangePasswordView(APIView):
    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.utils import timezone
        from .models import SecurityEvent
        from .security import record_security_event

        current = request.data.get("current_password", "")
        new = request.data.get("new_password", "")
        if not request.user.check_password(current):
            return Response({"current_password": ["Current password is incorrect."]}, status=400)
        try:
            validate_password(new, user=request.user)
        except DjangoValidationError as exc:
            return Response({"new_password": list(exc.messages)}, status=400)
        request.user.set_password(new)
        request.user.last_password_change_at = timezone.now()
        request.user.save(update_fields=["password", "last_password_change_at"])
        record_security_event(request, SecurityEvent.Type.PASSWORD_CHANGED, request.user)
        return Response({"detail": "Password changed successfully."})


class SecuritySettingsView(APIView):
    def get(self, request):
        return Response(
            {
                "email_verified": bool(request.user.email_verified_at),
                "email_verified_at": request.user.email_verified_at,
                "phone_verified": bool(request.user.phone_verified_at),
                "mfa_enabled": request.user.mfa_enabled,
                "last_password_change_at": request.user.last_password_change_at,
                "locked_until": request.user.locked_until,
            }
        )

    def patch(self, request):
        from .models import SecurityEvent
        from .security import record_security_event

        if "mfa_enabled" not in request.data:
            return Response({"detail": "mfa_enabled is required."}, status=400)
        if not request.user.check_password(request.data.get("password", "")):
            return Response({"password": ["Password confirmation is required."]}, status=400)
        enabled = str(request.data.get("mfa_enabled")).lower() in {"1", "true", "yes", "on"}
        request.user.mfa_enabled = enabled
        request.user.save(update_fields=["mfa_enabled"])
        record_security_event(
            request,
            SecurityEvent.Type.MFA_ENABLED if enabled else SecurityEvent.Type.MFA_DISABLED,
            request.user,
        )
        return Response({"mfa_enabled": enabled})


class RequestPhoneVerificationView(APIView):
    """Send an expiring verification code to the signed-in user's phone."""

    def post(self, request):
        from django.conf import settings
        from .models import OneTimeToken
        from .security import issue_token

        phone = str(request.user.phone or "").strip()
        if not phone:
            return Response({"phone": ["Add a phone number to your profile first."]}, status=400)
        if request.user.phone_verified_at:
            return Response({"detail": "Phone number is already verified."})
        token, code = issue_token(
            request.user,
            OneTimeToken.Purpose.PHONE_VERIFICATION,
            request=request,
            minutes=int(getattr(settings, "PHONE_VERIFICATION_MINUTES", 10)),
            numeric=True,
            metadata={"phone": phone},
        )
        delivery = "sms"
        try:
            from communication.providers import send_sms

            send_sms(
                phone,
                "MyDoctor phone verification",
                f"Your MyDoctor verification code is {code}. It expires in {getattr(settings, 'PHONE_VERIFICATION_MINUTES', 10)} minutes.",
                {"purpose": "phone_verification", "token_id": str(token.public_id)},
            )
        except Exception:
            # Local/demo installations have no SMS credentials. The code is only
            # exposed while DEBUG is enabled so production never leaks it.
            delivery = "development"
        payload = {"detail": "Verification code sent.", "token_id": str(token.public_id), "delivery": delivery}
        if getattr(settings, "DEBUG", False) and delivery == "development":
            payload["debug_code"] = code
        return Response(payload)


class VerifyPhoneView(APIView):
    def post(self, request):
        from django.utils import timezone
        from .models import OneTimeToken, SecurityEvent
        from .security import consume_token, record_security_event

        token_id = request.data.get("token_id")
        code = request.data.get("code")
        if not token_id or not code:
            return Response({"detail": "token_id and code are required."}, status=400)
        user = consume_token(token_id, code, OneTimeToken.Purpose.PHONE_VERIFICATION)
        if user.pk != request.user.pk:
            return Response({"detail": "This code belongs to another account."}, status=403)
        user.phone_verified_at = timezone.now()
        user.save(update_fields=["phone_verified_at"])
        record_security_event(request, SecurityEvent.Type.PHONE_VERIFIED, user)
        return Response({"detail": "Phone number verified successfully.", "phone_verified": True})


class LogoutView(APIView):
    """Blacklist the supplied refresh token and record a security event."""

    def post(self, request):
        from .models import SecurityEvent
        from .security import record_security_event

        raw = request.data.get("refresh")
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except Exception:
                # Logout stays idempotent even when the token was already revoked.
                pass
        record_security_event(request, SecurityEvent.Type.LOGOUT, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionListRevokeView(APIView):
    """List issued refresh tokens and allow revoking one or every session."""

    def get(self, request):
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        rows = OutstandingToken.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response([
            {
                "id": row.id,
                "jti": row.jti,
                "created_at": row.created_at,
                "expires_at": row.expires_at,
                "revoked": hasattr(row, "blacklistedtoken"),
            }
            for row in rows
        ])

    def post(self, request):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
        from .models import SecurityEvent
        from .security import record_security_event

        token_id = request.data.get("token_id")
        rows = OutstandingToken.objects.filter(user=request.user)
        if token_id not in (None, "", "all"):
            rows = rows.filter(pk=token_id)
        count = 0
        for row in rows:
            _, created = BlacklistedToken.objects.get_or_create(token=row)
            count += int(created)
        record_security_event(request, SecurityEvent.Type.SESSION_REVOKED, request.user, revoked=count)
        return Response({"revoked": count})


class MySecurityEventsView(APIView):
    def get(self, request):
        rows = request.user.security_events.all()[:50]
        return Response(
            [
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "ip_address": row.ip_address,
                    "user_agent": row.user_agent,
                    "detail": row.detail,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        )
