from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsRole
from accounts.roles import CLINICAL_ROLES
from clinical.services import resolve_patient_access
from governance.models import AuditEvent
from governance.services import audit

from .fhir import FHIR_FORMAT, FHIR_VERSION, patient_summary_bundle
from .models import OutboxEvent, TerminologyConcept
from .serializers import OutboxEventSerializer, TerminologyConceptSerializer


class CapabilityStatementView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "resourceType": "CapabilityStatement",
                "status": "active",
                "kind": "instance",
                "date": timezone.now().date().isoformat(),
                "publisher": "HealthPilot Platform",
                "description": FHIR_FORMAT,
                "fhirVersion": FHIR_VERSION,
                "format": ["json"],
                "rest": [
                    {
                        "mode": "server",
                        "security": {
                            "cors": True,
                            "description": "JWT authentication plus role, care-relationship, consent, and audit controls.",
                        },
                        "resource": [
                            {"type": resource_type, "interaction": [{"code": "read"}]}
                            for resource_type in [
                                "Patient",
                                "AllergyIntolerance",
                                "Condition",
                                "MedicationStatement",
                                "Observation",
                                "Encounter",
                                "CarePlan",
                                "Consent",
                            ]
                        ],
                    }
                ],
            }
        )


class PatientSummaryExportView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", *sorted(CLINICAL_ROLES), "admin"]

    def get(self, request, patient_id):
        patient = get_object_or_404(User, pk=patient_id, role=User.Role.PATIENT)
        allowed, emergency, reason = resolve_patient_access(request, patient)
        if not allowed:
            return Response({"detail": reason}, status=403)
        bundle = patient_summary_bundle(patient, viewer=request.user)
        audit(
            actor=request.user,
            patient=patient,
            action="interoperability.fhir_summary.exported",
            resource_type="FHIRBundle",
            resource_id=str(patient.id),
            purpose="emergency" if emergency else "treatment",
            decision=AuditEvent.Decision.ALLOW,
            emergency_access=emergency,
            metadata={"resources": bundle["total"], "format": "FHIR R4-aligned draft"},
            request=request,
        )
        return Response(bundle, content_type="application/fhir+json")


class TerminologySearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = TerminologyConcept.objects.filter(active=True)
        query = request.query_params.get("q", "").strip()
        system = request.query_params.get("system", "").strip()
        category = request.query_params.get("category", "").strip()
        if system:
            qs = qs.filter(system=system)
        if category:
            qs = qs.filter(category=category)
        if query:
            qs = qs.filter(Q(code__icontains=query) | Q(display__icontains=query))
        try:
            limit = min(max(int(request.query_params.get("limit", 50)), 1), 200)
        except ValueError:
            limit = 50
        return Response(TerminologyConceptSerializer(qs[:limit], many=True).data)


class TerminologyConceptManageView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def post(self, request):
        serializer = TerminologyConceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        concept = serializer.save()
        audit(actor=request.user, action="terminology.concept.created", resource=concept, purpose="terminology_governance", request=request)
        return Response(TerminologyConceptSerializer(concept).data, status=201)

    def patch(self, request, pk):
        concept = get_object_or_404(TerminologyConcept, pk=pk)
        serializer = TerminologyConceptSerializer(concept, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        concept = serializer.save()
        audit(actor=request.user, action="terminology.concept.updated", resource=concept, purpose="terminology_governance", request=request)
        return Response(TerminologyConceptSerializer(concept).data)


class OutboxEventListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        qs = OutboxEvent.objects.select_related("actor", "patient")
        event_status = request.query_params.get("status")
        event_type = request.query_params.get("event_type")
        if event_status:
            qs = qs.filter(status=event_status)
        if event_type:
            qs = qs.filter(event_type__icontains=event_type)
        try:
            limit = min(max(int(request.query_params.get("limit", 200)), 1), 1000)
        except ValueError:
            limit = 200
        return Response(OutboxEventSerializer(qs[:limit], many=True).data)
