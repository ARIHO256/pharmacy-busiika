from django.utils import timezone
from rest_framework import serializers

from config.uploads import validate_credential_upload

from accounts.models import User
from enterprise.access import can_review_compliance, is_platform_super_admin

from .models import (
    CareRelationship,
    Organization,
    OrganizationLocation,
    PractitionerCredential,
    PractitionerRole,
)


class OrganizationLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationLocation
        fields = "__all__"
        read_only_fields = ["organization"]


class OrganizationSerializer(serializers.ModelSerializer):
    locations = OrganizationLocationSerializer(many=True, read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    license_document = serializers.FileField(write_only=True, required=False, allow_null=True, validators=[validate_credential_upload])
    license_document_url = serializers.SerializerMethodField()

    def get_license_document_url(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not obj.license_document or not user or not user.is_authenticated:
            return None
        if not (is_platform_super_admin(user) or can_review_compliance(user)) and obj.owner_id != user.id:
            return None
        path = f"/api/registry/organizations/{obj.public_id}/license-document/"
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = Organization
        fields = [
            "id",
            "public_id",
            "owner",
            "owner_email",
            "legal_name",
            "trading_name",
            "organization_type",
            "license_number",
            "license_issued_on",
            "license_expires_on",
            "license_document",
            "license_document_url",
            "services_description",
            "issuing_authority",
            "status",
            "contact_email",
            "phone",
            "address",
            "district",
            "country_code",
            "active",
            "locations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner", "status", "public_id", "created_at", "updated_at"]

    def validate(self, attrs):
        organization_type = attrs.get(
            "organization_type", getattr(self.instance, "organization_type", None)
        )
        license_number = attrs.get(
            "license_number", getattr(self.instance, "license_number", "")
        ).strip()
        if organization_type and license_number:
            duplicates = Organization.objects.filter(
                organization_type=organization_type, license_number=license_number
            )
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {"license_number": "This licence number is already registered for this organization type."}
                )
        issued = attrs.get("license_issued_on", getattr(self.instance, "license_issued_on", None))
        expires = attrs.get("license_expires_on", getattr(self.instance, "license_expires_on", None))
        if issued and expires and expires <= issued:
            raise serializers.ValidationError({"license_expires_on": "Expiry must be after issue date."})
        attrs["license_number"] = license_number
        return attrs


class PractitionerCredentialSerializer(serializers.ModelSerializer):
    practitioner_name = serializers.SerializerMethodField()
    verified_by_email = serializers.EmailField(source="verified_by.email", read_only=True)
    document = serializers.FileField(write_only=True, required=False, allow_null=True, validators=[validate_credential_upload])
    document_url = serializers.SerializerMethodField()

    def get_document_url(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not obj.document or not user or not user.is_authenticated:
            return None
        if not (is_platform_super_admin(user) or can_review_compliance(user)) and obj.practitioner_id != user.id:
            return None
        path = f"/api/registry/credentials/{obj.pk}/document/"
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = PractitionerCredential
        fields = [
            "id", "practitioner", "practitioner_name", "credential_type", "identifier",
            "issuer", "title", "issued_on", "expires_on", "status", "document",
            "document_url", "verified_by", "verified_by_email", "verified_at", "created_at",
        ]
        read_only_fields = ["practitioner", "status", "verified_by", "verified_at", "created_at"]

    def get_practitioner_name(self, obj):
        return obj.practitioner.get_full_name() or obj.practitioner.email

    def validate(self, attrs):
        issued = attrs.get("issued_on", getattr(self.instance, "issued_on", None))
        expires = attrs.get("expires_on", getattr(self.instance, "expires_on", None))
        if issued and expires and expires <= issued:
            raise serializers.ValidationError({"expires_on": "Expiry must be after issue date."})
        return attrs


class PractitionerRoleSerializer(serializers.ModelSerializer):
    practitioner_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)

    class Meta:
        model = PractitionerRole
        fields = "__all__"
        read_only_fields = ["practitioner"]

    def get_practitioner_name(self, obj):
        return obj.practitioner.get_full_name() or obj.practitioner.email

    def validate(self, attrs):
        organization = attrs.get("organization", getattr(self.instance, "organization", None))
        location = attrs.get("location", getattr(self.instance, "location", None))
        if location and organization and location.organization_id != organization.id:
            raise serializers.ValidationError({"location": "Location belongs to another organization."})
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})
        return attrs


class CareRelationshipSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)

    class Meta:
        model = CareRelationship
        fields = "__all__"
        read_only_fields = [
            "patient",
            "practitioner",
            "appointment",
            "organization",
            "relationship_type",
            "purpose",
            "status",
            "starts_at",
            "ends_at",
            "created_by",
        ]

    def get_patient_name(self, obj):
        return obj.patient.get_full_name() or obj.patient.email

    def get_practitioner_name(self, obj):
        return obj.practitioner.get_full_name() or obj.practitioner.email
