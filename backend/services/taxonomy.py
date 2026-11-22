from django.db.models import Q

from .medicine_attributes import FIELDS_BY_NODE
from .models import MedicineTaxonomyNode, MedicineTaxonomyOverride


def scoped_nodes(pharmacy_id):
    return MedicineTaxonomyNode.objects.filter(Q(pharmacy__isnull=True) | Q(pharmacy_id=pharmacy_id))


def attribute_fields(node):
    if node is None:
        return ()
    return node.attribute_fields if node.pharmacy_id else FIELDS_BY_NODE.get(node.pk, ())


def is_archived(node, pharmacy_id):
    ids = [node.pk]
    if node.parent_id:
        ids.append(node.parent_id)
        if node.parent.parent_id:
            ids.append(node.parent.parent_id)
    return MedicineTaxonomyOverride.objects.filter(pharmacy_id=pharmacy_id, node_id__in=ids, archived=True).exists()


def catalogue(pharmacy_id):
    nodes = list(scoped_nodes(pharmacy_id))
    nodes_by_id = {node.pk: node for node in nodes}
    overrides = {row.node_id: row for row in MedicineTaxonomyOverride.objects.filter(pharmacy_id=pharmacy_id)}
    rows = []
    for node in nodes:
        override = overrides.get(node.pk)
        parent = nodes_by_id.get(node.parent_id)
        ancestry = [overrides.get(key) for key in (node.pk, node.parent_id, parent.parent_id if parent else None)]
        rows.append({
            "node_id": node.pk,
            "parent": node.parent_id,
            "level": node.level,
            "name": override.name if override and override.name else node.name,
            "image_url": node.image_url,
            "attribute_fields": attribute_fields(node),
            "archived": any(row and row.archived for row in ancestry),
            "directly_archived": bool(override and override.archived),
        })
    return rows
