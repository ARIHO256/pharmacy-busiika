import csv
from pathlib import Path

from django.db import migrations


def seed_taxonomy(apps, schema_editor):
    taxonomy = apps.get_model("services", "MedicineTaxonomyNode")
    seed = Path(__file__).with_name("pharmacy_taxonomy_seed.csv")
    with seed.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            node_id = row.pop("node_id")
            row["parent_id"] = row["parent_id"] or None
            taxonomy.objects.using(schema_editor.connection.alias).update_or_create(node_id=node_id, defaults=row)


class Migration(migrations.Migration):
    dependencies = [("services", "0010_medicinetaxonomynode_medicine_taxonomy_node")]
    operations = [migrations.RunPython(seed_taxonomy, migrations.RunPython.noop)]
