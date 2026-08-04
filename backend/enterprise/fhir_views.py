import base64
import hashlib
import hmac
import os
import uuid
import json
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .authentication import PartnerTokenAuthentication
from .models import FHIRResource, PartnerAccessToken, PartnerApplication
from .services import fhir_bundle, upsert_fhir_resource


class HasFHIRScope(BasePermission):
    def has_permission(self, request, view):
        scopes = getattr(request, "partner_scopes", set())
        required = "fhir.write" if request.method in {"POST", "PUT", "PATCH", "DELETE"} else "fhir.read"
        return required in scopes or "fhir.*" in scopes


class CapabilityStatementView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            "resourceType": "CapabilityStatement",
            "status": "active",
            "date": "2026-08-04",
            "kind": "instance",
            "software": {"name": "MyDoctor HealthOS FHIR Gateway", "version": "1.0.0"},
            "implementation": {"description": "FHIR R4 persistence and partner gateway"},
            "fhirVersion": "4.0.1",
            "format": ["json", "application/fhir+json"],
            "rest": [{
                "mode": "server",
                "security": {"cors": True, "service": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/restful-security-service", "code": "OAuth"}]}]},
                "resource": [{"type": resource, "interaction": [{"code": action} for action in ["read", "search-type", "create", "update"]]} for resource in ["Patient", "Encounter", "Observation", "Condition", "AllergyIntolerance", "MedicationRequest", "DiagnosticReport", "ServiceRequest", "Appointment", "Organization", "Practitioner", "PractitionerRole", "DocumentReference"]],
            }],
        }, content_type="application/fhir+json")


class FHIRTypeView(APIView):
    authentication_classes = [PartnerTokenAuthentication]
    permission_classes = [HasFHIRScope]

    def get(self, request, resource_type):
        queryset = FHIRResource.objects.filter(resource_type=resource_type, status="active").order_by("-last_updated")
        patient = request.query_params.get("patient") or request.query_params.get("subject")
        organization = request.query_params.get("organization")
        identifier = request.query_params.get("identifier")
        if patient:
            queryset = queryset.filter(Q(patient_id=patient) | Q(data__subject__reference=f"Patient/{patient}"))
        if organization:
            queryset = queryset.filter(organization_id=organization)
        # JSON identifier search is applied in Python for SQLite/PostgreSQL portability.
        latest = {}
        for row in queryset[:1000]:
            if identifier and identifier.lower() not in json.dumps(row.data).lower():
                continue
            latest.setdefault(str(row.logical_id), row)
        return Response(fhir_bundle(list(latest.values())), content_type="application/fhir+json")

    def post(self, request, resource_type):
        data = dict(request.data)
        if data.get("resourceType") and data["resourceType"] != resource_type:
            return Response({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "invalid", "diagnostics": "resourceType does not match URL."}]}, status=400, content_type="application/fhir+json")
        row = upsert_fhir_resource(resource_type, data)
        response = {**row.data, "id": str(row.logical_id), "meta": {"versionId": str(row.version_id), "lastUpdated": row.last_updated.isoformat()}}
        return Response(response, status=status.HTTP_201_CREATED, content_type="application/fhir+json", headers={"Location": f"{resource_type}/{row.logical_id}/_history/{row.version_id}"})


class FHIRInstanceView(APIView):
    authentication_classes = [PartnerTokenAuthentication]
    permission_classes = [HasFHIRScope]

    def get(self, request, resource_type, logical_id):
        row = get_object_or_404(FHIRResource.objects.filter(resource_type=resource_type, logical_id=logical_id).order_by("-version_id"))
        return Response({**row.data, "id": str(row.logical_id), "meta": {"versionId": str(row.version_id), "lastUpdated": row.last_updated.isoformat()}}, content_type="application/fhir+json")

    def put(self, request, resource_type, logical_id):
        data = dict(request.data)
        row = upsert_fhir_resource(resource_type, data, logical_id=logical_id)
        return Response({**row.data, "id": str(row.logical_id), "meta": {"versionId": str(row.version_id), "lastUpdated": row.last_updated.isoformat()}}, content_type="application/fhir+json")

    def delete(self, request, resource_type, logical_id):
        latest = get_object_or_404(FHIRResource.objects.filter(resource_type=resource_type, logical_id=logical_id).order_by("-version_id"))
        latest.status = "deleted"
        latest.save(update_fields=["status", "last_updated"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FHIRHistoryView(APIView):
    authentication_classes = [PartnerTokenAuthentication]
    permission_classes = [HasFHIRScope]

    def get(self, request, resource_type, logical_id):
        rows = FHIRResource.objects.filter(resource_type=resource_type, logical_id=logical_id).order_by("-version_id")
        return Response(fhir_bundle(rows), content_type="application/fhir+json")


class SmartConfigurationView(APIView):
    """SMART App Launch discovery metadata for partner applications."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        root = request.build_absolute_uri("/api/v1/fhir/").rstrip("/")
        return Response({
            "issuer": root,
            "jwks_uri": request.build_absolute_uri("/api/v1/fhir/.well-known/jwks.json"),
            "token_endpoint": request.build_absolute_uri("/api/v1/fhir/oauth/token"),
            "capabilities": ["client-confidential-symmetric", "context-standalone-patient", "permission-v2"],
            "grant_types_supported": ["client_credentials"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
            "scopes_supported": [
                "fhir.read", "fhir.write", "fhir.*", "patient/*.read", "user/*.read",
                "launch/patient", "openid", "profile", "offline_access",
            ],
            "response_types_supported": ["token"],
        })


class SmartJwksView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        # Partner access tokens are opaque bearer tokens. An empty JWKS is valid
        # discovery metadata and avoids publishing secrets as asymmetric keys.
        return Response({"keys": []})


class SmartTokenView(APIView):
    """Issue short-lived scoped partner tokens using client credentials.

    Configure secrets as a JSON object in PARTNER_CLIENT_SECRETS_JSON where keys
    are PartnerApplication.client_id values. Only scopes registered on the app
    can be requested. This is deliberately an opaque-token implementation.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        client_id = str(request.data.get("client_id") or "")
        client_secret = str(request.data.get("client_secret") or "")
        header = request.headers.get("Authorization", "")
        if header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
                client_id, client_secret = decoded.split(":", 1)
            except Exception:
                return Response({"error": "invalid_client"}, status=status.HTTP_401_UNAUTHORIZED)
        app = PartnerApplication.objects.filter(client_id=client_id, active=True).first()
        if not app:
            return Response({"error": "invalid_client"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            configured = json.loads(os.getenv("PARTNER_CLIENT_SECRETS_JSON", "{}"))
        except json.JSONDecodeError:
            configured = {}
        expected = str(configured.get(client_id) or "")
        if not expected or not hmac.compare_digest(expected, client_secret):
            return Response({"error": "invalid_client"}, status=status.HTTP_401_UNAUTHORIZED)
        if request.data.get("grant_type", "client_credentials") != "client_credentials":
            return Response({"error": "unsupported_grant_type"}, status=status.HTTP_400_BAD_REQUEST)
        requested = set(str(request.data.get("scope") or "").split()) or set(app.scopes or [])
        allowed = set(app.scopes or [])
        if not requested.issubset(allowed):
            return Response({"error": "invalid_scope", "allowed_scopes": sorted(allowed)}, status=status.HTTP_400_BAD_REQUEST)
        ttl = max(5, min(int(request.data.get("ttl_minutes") or os.getenv("FHIR_TOKEN_TTL_MINUTES", "60")), 1440))
        token, raw = PartnerAccessToken.issue(app, sorted(requested), ttl_minutes=ttl)
        return Response({
            "access_token": raw,
            "token_type": "Bearer",
            "expires_in": ttl * 60,
            "scope": " ".join(token.scopes),
            "client_id": app.client_id,
        })


class FHIRVersionView(APIView):
    authentication_classes = [PartnerTokenAuthentication]
    permission_classes = [HasFHIRScope]

    def get(self, request, resource_type, logical_id, version_id):
        row = get_object_or_404(
            FHIRResource,
            resource_type=resource_type,
            logical_id=logical_id,
            version_id=version_id,
        )
        return Response({
            **row.data,
            "id": str(row.logical_id),
            "meta": {"versionId": str(row.version_id), "lastUpdated": row.last_updated.isoformat()},
        }, content_type="application/fhir+json")
