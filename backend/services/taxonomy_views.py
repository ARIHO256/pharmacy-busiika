from uuid import uuid4

from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from governance.services import audit
from accounts.models import User
from operations.serializers import StrictSerializer
from registry.models import Organization
from workforce.models import StaffMembership

from .models import MedicineTaxonomyNode as Node, MedicineTaxonomyOverride
from .taxonomy import attribute_fields, catalogue, is_archived, scoped_nodes


class AttributeInput(StrictSerializer):
    label = serializers.CharField(max_length=80)
    type = serializers.ChoiceField(choices=("text", "integer"))


class AddNode(StrictSerializer):
    name = serializers.CharField(max_length=200)
    level = serializers.ChoiceField(choices=Node.Level.values)
    parent = serializers.SlugField(max_length=220, required=False, allow_null=True)
    copy_from = serializers.SlugField(max_length=220, required=False)
    fields = AttributeInput(many=True, required=False, max_length=20)


class UpdateNode(StrictSerializer):
    name = serializers.CharField(max_length=200, required=False)
    archived = serializers.BooleanField(required=False)


def managed_pharmacies(user):
    if user.role not in {"pharmacy", "hospital", "facility_manager"}:
        raise PermissionDenied("Only pharmacy owners and authorized facility managers can manage taxonomy.")
    managed = Q(owner=user)
    parent = Q(parent_facility__owner=user)
    if user.role == "facility_manager":
        today = timezone.localdate()
        scope = StaffMembership.objects.filter(
            user=user, role="facility_manager", status="active",
            organization__active=True, organization__status="verified",
        ).filter(Q(starts_on__isnull=True) | Q(starts_on__lte=today)).filter(
            Q(ends_on__isnull=True) | Q(ends_on__gte=today),
        ).values("organization_id")
        managed |= Q(pk__in=scope)
        parent |= Q(parent_facility__in=scope)
    return Organization.objects.filter(
        managed | parent, organization_type="pharmacy", owner__role="pharmacy", active=True, status="verified",
    ).filter(
        Q(parent_facility__isnull=True) | Q(parent_facility__active=True, parent_facility__status="verified"),
    ).distinct().order_by("legal_name", "pk")


def selected_pharmacy(request, *, lock=False):
    choices = list(managed_pharmacies(request.user))
    selection = request.query_params.get("organization")
    if selection is not None:
        match = next((org for org in choices if str(org.pk) == selection), None)
    else:
        match = choices[0] if choices else None
    if match is None:
        raise PermissionDenied("Select a verified pharmacy you manage.")
    if lock:
        User.objects.select_for_update().get(pk=match.owner_id)
    return choices, match


def validate_name(pharmacy_id, *, parent, name, ignore=None):
    if any(row["parent"] == parent and row["node_id"] != ignore and row["name"].casefold() == name.casefold()
           for row in catalogue(pharmacy_id)):
        raise ValidationError({"name": "A node with this name already exists under this parent."})


def custom_fields(values, pharmacy_id):
    copied_id = values.get("copy_from")
    entered = values.get("fields", [])
    if values["level"] != Node.Level.SUBCATEGORY:
        if copied_id or entered:
            raise ValidationError("Product fields belong to subcategories.")
        return []
    if copied_id and entered:
        raise ValidationError("Choose a template or enter your own product fields.")
    if copied_id:
        source = get_object_or_404(scoped_nodes(pharmacy_id), pk=copied_id, level=Node.Level.SUBCATEGORY)
        return list(attribute_fields(source))
    definitions = []
    labels = set()
    for number, field in enumerate(entered, start=1):
        label = field["label"].casefold()
        if label in labels:
            raise ValidationError({"fields": "Use distinct field labels."})
        labels.add(label)
        definition = {"key": f"custom_{number}", **field}
        if field["type"] == "integer":
            definition["min"] = 1
        definitions.append(definition)
    return definitions


class TaxonomyManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        choices, pharmacy = selected_pharmacy(request)
        return Response({
            "organizations": [{"id": org.pk, "name": org.legal_name} for org in choices],
            "organization": pharmacy.pk,
            "nodes": catalogue(pharmacy.owner_id),
        })

    @transaction.atomic
    def post(self, request):
        _, pharmacy = selected_pharmacy(request, lock=True)
        serializer = AddNode(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        pharmacy_id = pharmacy.owner_id
        parent_id = values.get("parent")
        level = values["level"]
        if level == Node.Level.FAMILY:
            if parent_id:
                raise ValidationError({"parent": "A product family is a top-level node."})
        else:
            parent = get_object_or_404(scoped_nodes(pharmacy_id), pk=parent_id, level=level - 1)
            if is_archived(parent, pharmacy_id):
                raise ValidationError({"parent": "Restore the parent before adding a child."})
        validate_name(pharmacy_id, parent=parent_id, name=values["name"])
        fields = custom_fields(values, pharmacy_id)
        sort_order = scoped_nodes(pharmacy_id).aggregate(last=Max("sort_order"))["last"] or 0
        node = Node.objects.create(
            node_id=f"pharmacy-node-{uuid4().hex}", pharmacy_id=pharmacy_id, parent_id=parent_id,
            name=values["name"], level=level, sort_order=sort_order + 1, attribute_fields=fields,
        )
        audit(actor=request.user, action="pharmacy.taxonomy.created", resource=node, purpose="operations",
              metadata={"organization_id": pharmacy.pk}, request=request)
        return Response({"node_id": node.pk}, status=201)


class TaxonomyNodeManagementView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, node_id):
        _, pharmacy = selected_pharmacy(request, lock=True)
        pharmacy_id = pharmacy.owner_id
        node = get_object_or_404(scoped_nodes(pharmacy_id), pk=node_id)
        serializer = UpdateNode(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if not values:
            raise ValidationError("Enter a new name or change the archive status.")
        if "name" in values:
            validate_name(pharmacy_id, parent=node.parent_id, name=values["name"], ignore=node.pk)
        MedicineTaxonomyOverride.objects.update_or_create(pharmacy_id=pharmacy_id, node=node, defaults=values)
        audit(actor=request.user, action="pharmacy.taxonomy.updated", resource=node, purpose="operations",
              metadata={"organization_id": pharmacy.pk, **values}, request=request)
        return Response({"node_id": node.pk})
