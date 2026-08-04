from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from config.uploads import validate_credential_upload
from enterprise.access import can_review_compliance, is_platform_super_admin

from .models import (
    DoctorProfile,
    PatientProfile,
    PatientRelationship,
    ProfileStatus,
    ProviderProfile,
    StaffProfile,
    User,
)
from .roles import PROFESSIONAL_ROLES, PUBLIC_REGISTRATION_ROLES


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    verification_status = serializers.SerializerMethodField()
    active_context = serializers.SerializerMethodField()
    available_contexts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "role",
            "role_label",
            "phone",
            "is_verified",
            "email_verified_at",
            "phone_verified_at",
            "mfa_enabled",
            "verification_status",
            "active_context",
            "available_contexts",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "role_label",
            "is_verified",
            "email_verified_at",
            "phone_verified_at",
            "mfa_enabled",
            "verification_status",
            "active_context",
            "available_contexts",
            "date_joined",
        ]


    def get_active_context(self, obj):
        try:
            from enterprise.access import active_context_for
            from enterprise.serializers import RoleContextSerializer
            context = active_context_for(obj)
            return RoleContextSerializer(context).data if context else None
        except Exception:
            return None

    def get_available_contexts(self, obj):
        try:
            from enterprise.serializers import RoleContextSerializer
            return RoleContextSerializer(obj.role_contexts.filter(active=True).select_related("organization", "location", "department"), many=True).data
        except Exception:
            return []

    def get_verification_status(self, obj):
        if obj.role == User.Role.DOCTOR:
            return getattr(getattr(obj, "doctor_profile", None), "status", ProfileStatus.PENDING)
        if obj.role in (PROFESSIONAL_ROLES - {User.Role.DOCTOR}):
            return getattr(getattr(obj, "staff_profile", None), "status", ProfileStatus.PENDING)
        if obj.role in {
            User.Role.PHARMACY,
            User.Role.LAB,
            User.Role.HOSPITAL,
            User.Role.INSURANCE,
        }:
            return getattr(getattr(obj, "provider_profile", None), "status", ProfileStatus.PENDING)
        return "verified" if obj.is_verified else "active"


class RegisterSerializer(serializers.Serializer):
    """Single public registration flow with strict role-specific requirements."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=10, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30)
    role = serializers.ChoiceField(choices=sorted(PUBLIC_REGISTRATION_ROLES))

    # Patient
    location = serializers.CharField(max_length=180, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    # Doctor
    year_of_completion = serializers.IntegerField(required=False, min_value=1950, max_value=2100)
    university = serializers.CharField(max_length=220, required=False, allow_blank=True)
    cadre = serializers.ChoiceField(
        choices=DoctorProfile.Cadre.choices, required=False, allow_blank=True
    )
    specialization = serializers.CharField(max_length=120, required=False, allow_blank=True)
    license_number = serializers.CharField(max_length=140, required=False, allow_blank=True)
    license_issuer = serializers.CharField(max_length=180, required=False, allow_blank=True)
    license_issued_on = serializers.DateField(required=False, allow_null=True)
    license_expires_on = serializers.DateField(required=False, allow_null=True)
    license_document = serializers.FileField(required=False, allow_null=True, validators=[validate_credential_upload])
    workplace = serializers.CharField(max_length=220, required=False, allow_blank=True)
    consultation_fee = serializers.IntegerField(required=False, min_value=0)

    # Organization
    organization_type = serializers.ChoiceField(
        choices=ProviderProfile.OrganizationType.choices,
        required=False,
    )
    organization_name = serializers.CharField(max_length=220, required=False, allow_blank=True)
    district = serializers.CharField(max_length=120, required=False, allow_blank=True)
    services_description = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_license_document(self, value):
        if not value:
            return value
        allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        content_type = getattr(value, "content_type", "")
        if content_type and content_type not in allowed:
            raise serializers.ValidationError("Licence document must be a JPG, PNG, WEBP or PDF file.")
        if getattr(value, "size", 0) > 10 * 1024 * 1024:
            raise serializers.ValidationError("Licence document cannot exceed 10 MB.")
        return value

    def validate(self, attrs):
        candidate = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
            role=attrs.get("role", User.Role.PATIENT),
        )
        try:
            validate_password(attrs.get("password", ""), user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc

        role = attrs["role"]
        errors = {}
        if role == User.Role.PATIENT:
            if not (attrs.get("location", "").strip() or attrs.get("address", "").strip()):
                errors["location"] = "Provide the patient's location or address."
        elif role == User.Role.DOCTOR:
            required = {
                "year_of_completion": "Year of completion is required.",
                "university": "University of completion is required.",
                "cadre": "Professional cadre is required.",
                "license_number": "Practising licence number is required.",
                "license_document": "Practising licence photo or PDF is required.",
                "workplace": "Current hospital, clinic or pharmacy is required.",
                "consultation_fee": "Consultation fee is required.",
            }
            for field, message in required.items():
                value = attrs.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    errors[field] = message
            number = attrs.get("license_number", "").strip()
            if number and (
                DoctorProfile.objects.filter(license_number__iexact=number).exists()
                or StaffProfile.objects.filter(registration_number__iexact=number).exists()
            ):
                errors["license_number"] = "This professional registration number is already registered."
            expiry = attrs.get("license_expires_on")
            if expiry and expiry <= date.today():
                errors["license_expires_on"] = "A current practising licence is required."
        else:
            organization_types = {
                User.Role.HOSPITAL: attrs.get(
                    "organization_type", ProviderProfile.OrganizationType.HOSPITAL
                ),
                User.Role.PHARMACY: ProviderProfile.OrganizationType.PHARMACY,
                User.Role.LAB: ProviderProfile.OrganizationType.LABORATORY,
                User.Role.INSURANCE: ProviderProfile.OrganizationType.INSURER,
            }
            attrs["organization_type"] = organization_types[role]
            required = {
                "organization_name": "Organization name is required.",
                "license_number": "Registered licence number is required.",
                "license_issuer": "Licence issuing authority is required.",
                "license_expires_on": "Licence expiry date is required.",
                "license_document": "Organization licence photo or PDF is required.",
                "district": "District or location is required.",
                "address": "Organization address is required.",
                "services_description": "Describe the services offered.",
            }
            for field, message in required.items():
                value = attrs.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    errors[field] = message
            issued = attrs.get("license_issued_on")
            expiry = attrs.get("license_expires_on")
            if issued and expiry and expiry <= issued:
                errors["license_expires_on"] = "Expiry must be after the licence issue date."
            if expiry and expiry <= date.today():
                errors["license_expires_on"] = "A current organization operating licence is required."
            number = attrs.get("license_number", "").strip()
            if number and ProviderProfile.objects.filter(license_number__iexact=number).exists():
                errors["license_number"] = "This organization licence number is already registered."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        role = validated_data["role"]
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", "").strip(),
            last_name=validated_data.get("last_name", "").strip(),
            phone=validated_data.get("phone", "").strip(),
            role=role,
            is_verified=role == User.Role.PATIENT,
        )
        if role == User.Role.PATIENT:
            PatientProfile.objects.create(
                user=user,
                location=validated_data.get("location", "").strip(),
                address=validated_data.get("address", "").strip(),
            )
        elif role == User.Role.DOCTOR:
            profile = DoctorProfile.objects.create(
                user=user,
                year_of_completion=validated_data.get("year_of_completion"),
                university=validated_data.get("university", "").strip(),
                cadre=validated_data.get("cadre", ""),
                specialization=validated_data.get("specialization", "").strip(),
                license_number=validated_data.get("license_number", "").strip(),
                license_issuer=validated_data.get("license_issuer", "").strip(),
                license_expires_on=validated_data.get("license_expires_on"),
                license_document=validated_data.get("license_document"),
                hospital=validated_data.get("workplace", "").strip(),
                fees=validated_data.get("consultation_fee", 0),
                status=ProfileStatus.PENDING,
            )
            from registry.models import PractitionerCredential

            PractitionerCredential.objects.create(
                practitioner=user,
                credential_type=PractitionerCredential.Type.LICENSE,
                identifier=profile.license_number,
                issuer=profile.license_issuer or "Professional regulator",
                title=f"{profile.get_cadre_display() or 'Medical'} practising licence",
                expires_on=profile.license_expires_on,
                document=profile.license_document,
            )
        else:
            profile = ProviderProfile.objects.create(
                user=user,
                organization_type=validated_data["organization_type"],
                org_name=validated_data.get("organization_name", "").strip(),
                license_number=validated_data.get("license_number", "").strip(),
                license_issuer=validated_data.get("license_issuer", "").strip(),
                license_issued_on=validated_data.get("license_issued_on"),
                license_expires_on=validated_data.get("license_expires_on"),
                license_document=validated_data.get("license_document"),
                district=validated_data.get("district", "").strip(),
                address=validated_data.get("address", "").strip(),
                services_description=validated_data.get("services_description", "").strip(),
                status=ProfileStatus.PENDING,
            )
            from registry.services import sync_provider_organization

            sync_provider_organization(user, profile)
        return user


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = [
            "dob",
            "gender",
            "blood_group",
            "allergies",
            "medical_history",
            "emergency_contact",
            "location",
            "address",
        ]


class PatientRelationshipSerializer(serializers.ModelSerializer):
    patient_id = serializers.IntegerField(source="patient.id", read_only=True)
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    dob = serializers.DateField(source="patient.patient_profile.dob", read_only=True)
    gender = serializers.CharField(source="patient.patient_profile.gender", read_only=True)
    blood_group = serializers.CharField(source="patient.patient_profile.blood_group", read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    authority_document_url = serializers.SerializerMethodField()

    class Meta:
        model = PatientRelationship
        fields = [
            "id", "patient_id", "patient_name", "patient_email", "dob", "gender",
            "blood_group", "relationship", "status", "is_current", "can_book",
            "can_view_records", "can_manage_billing", "can_receive_notifications",
            "authority_document_url", "expires_at", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at"]

    def get_authority_document_url(self, obj):
        request = self.context.get("request")
        if not request or not obj.authority_document:
            return None
        user = request.user
        if not (is_platform_super_admin(user) or can_review_compliance(user)) and user.pk not in {obj.caregiver_id, obj.patient_id}:
            return None
        return request.build_absolute_uri(f"/api/auth/dependents/{obj.pk}/authority-document/")


class DependentCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    dob = serializers.DateField()
    gender = serializers.ChoiceField(choices=PatientProfile.Gender.choices, required=False, allow_blank=True)
    relationship = serializers.ChoiceField(choices=PatientRelationship.Relationship.choices)
    blood_group = serializers.CharField(max_length=5, required=False, allow_blank=True)
    allergies = serializers.CharField(required=False, allow_blank=True)
    medical_history = serializers.CharField(required=False, allow_blank=True)
    emergency_contact = serializers.CharField(max_length=50, required=False, allow_blank=True)
    location = serializers.CharField(max_length=180, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    can_book = serializers.BooleanField(default=True)
    can_view_records = serializers.BooleanField(default=True)
    can_manage_billing = serializers.BooleanField(default=True)
    can_receive_notifications = serializers.BooleanField(default=True)
    authority_document = serializers.FileField(required=False, allow_null=True, validators=[validate_credential_upload])
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_dob(self, value):
        if value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value

    def validate_authority_document(self, value):
        if not value:
            return value
        allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        content_type = getattr(value, "content_type", "")
        if content_type and content_type not in allowed:
            raise serializers.ValidationError("Authority evidence must be a JPG, PNG, WEBP or PDF file.")
        if getattr(value, "size", 0) > 10 * 1024 * 1024:
            raise serializers.ValidationError("Authority evidence cannot exceed 10 MB.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        import uuid

        caregiver = self.context["request"].user
        internal_email = f"dependent.{uuid.uuid4().hex}@patients.mydoctor.local"
        patient = User.objects.create(
            email=internal_email,
            first_name=validated_data["first_name"].strip(),
            last_name=validated_data["last_name"].strip(),
            role=User.Role.PATIENT,
            is_verified=True,
            is_active=True,
        )
        patient.set_unusable_password()
        patient.save(update_fields=["password"])
        PatientProfile.objects.create(
            user=patient,
            dob=validated_data["dob"],
            gender=validated_data.get("gender", ""),
            blood_group=validated_data.get("blood_group", ""),
            allergies=validated_data.get("allergies", ""),
            medical_history=validated_data.get("medical_history", ""),
            emergency_contact=validated_data.get("emergency_contact", ""),
            location=validated_data.get("location", ""),
            address=validated_data.get("address", ""),
        )
        age = (date.today() - validated_data["dob"]).days // 365
        # Minor dependents can be managed by the creating patient immediately.
        # Adult-caregiver authority always requires an explicit administrator
        # review, even when supporting evidence is uploaded.
        status_value = (
            PatientRelationship.Status.ACTIVE
            if age < 18
            else PatientRelationship.Status.PENDING
        )
        relationship = PatientRelationship.objects.create(
            caregiver=caregiver,
            patient=patient,
            relationship=validated_data["relationship"],
            status=status_value,
            can_book=validated_data.get("can_book", True),
            can_view_records=validated_data.get("can_view_records", True),
            can_manage_billing=validated_data.get("can_manage_billing", True),
            can_receive_notifications=validated_data.get("can_receive_notifications", True),
            authority_document=validated_data.get("authority_document"),
            notes=validated_data.get("notes", ""),
        )
        return relationship


class ProtectedCredentialMixin:
    license_document_url = serializers.SerializerMethodField()

    def get_license_document_url(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        owner = getattr(obj, "user", None)
        if not request or not user or not user.is_authenticated or owner is None:
            return None
        if not (is_platform_super_admin(user) or can_review_compliance(user)) and user.pk != owner.pk:
            return None
        from registry.models import PractitionerCredential

        credential = (
            PractitionerCredential.objects.filter(practitioner=owner)
            .exclude(document="")
            .order_by("-created_at")
            .first()
        )
        if credential is None or not credential.document:
            return None
        return request.build_absolute_uri(
            f"/api/registry/credentials/{credential.pk}/document/"
        )


class DoctorProfileSerializer(ProtectedCredentialMixin, serializers.ModelSerializer):
    license_document = serializers.FileField(write_only=True, required=False, allow_null=False, validators=[validate_credential_upload])
    certificates = serializers.FileField(write_only=True, required=False, allow_null=True, validators=[validate_credential_upload])
    certificates_uploaded = serializers.SerializerMethodField()

    class Meta:
        model = DoctorProfile
        fields = [
            "year_of_completion",
            "university",
            "cadre",
            "specialization",
            "hospital",
            "experience_years",
            "fees",
            "bio",
            "license_number",
            "license_issuer",
            "license_issued_on",
            "license_expires_on",
            "license_document",
            "license_document_url",
            "certificates",
            "certificates_uploaded",
            "status",
            "verification_notes",
            "average_rating",
        ]
        read_only_fields = [
            "license_document_url",
            "certificates_uploaded",
            "status",
            "verification_notes",
            "average_rating",
        ]

    def get_certificates_uploaded(self, obj):
        return bool(obj.certificates)

    def validate_license_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Practising licence number cannot be blank.")
        duplicates = DoctorProfile.objects.filter(license_number__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists() or StaffProfile.objects.filter(
            registration_number__iexact=value
        ).exists():
            raise serializers.ValidationError(
                "This professional registration number is already registered."
            )
        return value

    def validate_license_document(self, value):
        allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        content_type = getattr(value, "content_type", "")
        if content_type and content_type not in allowed:
            raise serializers.ValidationError(
                "Licence document must be a JPG, PNG, WEBP or PDF file."
            )
        if getattr(value, "size", 0) > 10 * 1024 * 1024:
            raise serializers.ValidationError("Licence document cannot exceed 10 MB.")
        return value

    def validate_license_expires_on(self, value):
        if value and value <= date.today():
            raise serializers.ValidationError("A current practising licence is required.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if "license_document" in attrs and attrs["license_document"] is None:
            raise serializers.ValidationError(
                {"license_document": "The practising licence document cannot be removed."}
            )
        licence_number = attrs.get(
            "license_number", getattr(instance, "license_number", "") if instance else ""
        )
        if attrs.get("license_document") and not str(licence_number or "").strip():
            raise serializers.ValidationError(
                {"license_number": "Provide the practising licence number with the document."}
            )
        return attrs


class ProviderProfileSerializer(serializers.ModelSerializer):
    license_document = serializers.FileField(write_only=True, required=False, allow_null=False, validators=[validate_credential_upload])
    license_document_url = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = [
            "organization_type",
            "org_name",
            "license_number",
            "license_issuer",
            "license_issued_on",
            "license_expires_on",
            "license_document",
            "license_document_url",
            "district",
            "address",
            "services_description",
            "status",
            "verification_notes",
        ]
        read_only_fields = ["license_document_url", "status", "verification_notes"]

    def get_license_document_url(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not request or not user or not user.is_authenticated:
            return None
        if not (is_platform_super_admin(user) or can_review_compliance(user)) and user.pk != obj.user_id:
            return None
        from registry.models import Organization

        organization = (
            Organization.objects.filter(owner=obj.user)
            .exclude(license_document="")
            .order_by("id")
            .first()
        )
        if organization is None or not organization.license_document:
            return None
        return request.build_absolute_uri(
            f"/api/registry/organizations/{organization.public_id}/license-document/"
        )

    def validate_organization_type(self, value):
        user = getattr(self.instance, "user", None)
        if user is None:
            request = self.context.get("request")
            user = getattr(request, "user", None)
        allowed = {
            User.Role.HOSPITAL: {
                ProviderProfile.OrganizationType.HOSPITAL,
                ProviderProfile.OrganizationType.CLINIC,
            },
            User.Role.PHARMACY: {ProviderProfile.OrganizationType.PHARMACY},
            User.Role.LAB: {ProviderProfile.OrganizationType.LABORATORY},
            User.Role.INSURANCE: {ProviderProfile.OrganizationType.INSURER},
        }.get(getattr(user, "role", None), set())
        if allowed and value not in allowed:
            raise serializers.ValidationError(
                "This organization type is not valid for the account role."
            )
        return value

    def validate_license_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Registered licence number cannot be blank.")

        from registry.models import Organization
        from registry.services import organization_type_for_role

        user = getattr(self.instance, "user", None)
        if user is None:
            request = self.context.get("request")
            user = getattr(request, "user", None)
        requested_type = self.initial_data.get("organization_type") or getattr(
            self.instance, "organization_type", None
        )
        allowed = {
            User.Role.HOSPITAL: {
                ProviderProfile.OrganizationType.HOSPITAL,
                ProviderProfile.OrganizationType.CLINIC,
            },
            User.Role.PHARMACY: {ProviderProfile.OrganizationType.PHARMACY},
            User.Role.LAB: {ProviderProfile.OrganizationType.LABORATORY},
            User.Role.INSURANCE: {ProviderProfile.OrganizationType.INSURER},
        }.get(getattr(user, "role", None), set())
        organization_type = (
            requested_type
            if requested_type in allowed
            else organization_type_for_role(getattr(user, "role", None))
        )
        if not organization_type:
            return value

        duplicates = Organization.objects.filter(
            organization_type=organization_type, license_number=value
        )
        if user and getattr(user, "pk", None):
            duplicates = duplicates.exclude(owner=user)
        if duplicates.exists():
            raise serializers.ValidationError(
                "This licence number is already registered for another organization."
            )
        return value

    def validate_license_document(self, value):
        if not value:
            return value
        allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        content_type = getattr(value, "content_type", "")
        if content_type and content_type not in allowed:
            raise serializers.ValidationError(
                "Licence document must be a JPG, PNG, WEBP or PDF file."
            )
        if getattr(value, "size", 0) > 10 * 1024 * 1024:
            raise serializers.ValidationError("Licence document cannot exceed 10 MB.")
        return value

    def validate(self, attrs):
        instance = self.instance
        user = getattr(instance, "user", None)
        allowed_types = {
            User.Role.HOSPITAL: {
                ProviderProfile.OrganizationType.HOSPITAL,
                ProviderProfile.OrganizationType.CLINIC,
            },
            User.Role.PHARMACY: {ProviderProfile.OrganizationType.PHARMACY},
            User.Role.LAB: {ProviderProfile.OrganizationType.LABORATORY},
            User.Role.INSURANCE: {ProviderProfile.OrganizationType.INSURER},
        }.get(getattr(user, "role", None), set())
        default_types = {
            User.Role.HOSPITAL: ProviderProfile.OrganizationType.HOSPITAL,
            User.Role.PHARMACY: ProviderProfile.OrganizationType.PHARMACY,
            User.Role.LAB: ProviderProfile.OrganizationType.LABORATORY,
            User.Role.INSURANCE: ProviderProfile.OrganizationType.INSURER,
        }
        current_type = attrs.get(
            "organization_type", getattr(instance, "organization_type", None)
        )
        if allowed_types and current_type not in allowed_types:
            attrs["organization_type"] = default_types[user.role]
        if "license_document" in attrs and attrs["license_document"] is None:
            raise serializers.ValidationError(
                {"license_document": "The organization licence document cannot be removed."}
            )
        number = attrs.get(
            "license_number", getattr(instance, "license_number", "") if instance else ""
        )
        if attrs.get("license_document") and not str(number or "").strip():
            raise serializers.ValidationError(
                {"license_number": "Provide the registered licence number with the document."}
            )
        labels = {
            "org_name": "Organization name",
            "district": "District or location",
            "address": "Physical address",
            "services_description": "Services description",
        }
        for field, label in labels.items():
            if field in attrs and not str(attrs.get(field) or "").strip():
                raise serializers.ValidationError({field: f"{label} cannot be blank."})
        return attrs


class StaffProfileSerializer(ProtectedCredentialMixin, serializers.ModelSerializer):
    license_document = serializers.FileField(write_only=True, required=False, allow_null=True, validators=[validate_credential_upload])

    class Meta:
        model = StaffProfile
        fields = [
            "employee_number",
            "cadre",
            "university",
            "year_of_completion",
            "qualification",
            "specialty",
            "workplace",
            "experience_years",
            "consultation_fee",
            "offers_appointments",
            "average_rating",
            "registration_number",
            "license_issuer",
            "license_issued_on",
            "license_expires_on",
            "license_document",
            "license_document_url",
            "bio",
            "status",
        ]
        read_only_fields = ["license_document_url", "status", "average_rating"]

    def validate_registration_number(self, value):
        value = value.strip()
        if not value:
            user = getattr(self.instance, "user", None)
            if getattr(user, "role", None) in PROFESSIONAL_ROLES:
                raise serializers.ValidationError(
                    "Professional registration number cannot be blank."
                )
            return value
        staff = StaffProfile.objects.filter(registration_number__iexact=value)
        if self.instance is not None:
            staff = staff.exclude(pk=self.instance.pk)
        if staff.exists() or DoctorProfile.objects.filter(license_number__iexact=value).exists():
            raise serializers.ValidationError(
                "This professional registration number is already in use."
            )
        return value

    def validate_license_expires_on(self, value):
        if value and value <= date.today():
            raise serializers.ValidationError("A current practising licence is required.")
        return value

    def validate_license_document(self, value):
        if not value:
            return value
        allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        content_type = getattr(value, "content_type", "")
        if content_type and content_type not in allowed:
            raise serializers.ValidationError(
                "Licence document must be a JPG, PNG, WEBP or PDF file."
            )
        if getattr(value, "size", 0) > 10 * 1024 * 1024:
            raise serializers.ValidationError("Licence document cannot exceed 10 MB.")
        return value

    def validate(self, attrs):
        instance = self.instance
        user = getattr(instance, "user", None)
        if (
            "license_document" in attrs
            and attrs["license_document"] is None
            and getattr(user, "role", None) in PROFESSIONAL_ROLES
        ):
            raise serializers.ValidationError(
                {"license_document": "The practising licence document cannot be removed."}
            )
        number = attrs.get(
            "registration_number",
            getattr(instance, "registration_number", "") if instance else "",
        )
        if attrs.get("license_document") and not str(number or "").strip():
            raise serializers.ValidationError(
                {"registration_number": "Provide the registration number with the document."}
            )
        return attrs


class PublicDoctorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    role = serializers.CharField()
    role_label = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    cadre = serializers.CharField()
    specialization = serializers.CharField()
    hospital = serializers.CharField()
    experience_years = serializers.IntegerField()
    fees = serializers.IntegerField()
    bio = serializers.CharField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)


class PublicDoctorDetailSerializer(PublicDoctorSerializer):
    status = serializers.CharField()
