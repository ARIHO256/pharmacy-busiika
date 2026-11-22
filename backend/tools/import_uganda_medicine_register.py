"""Import the curated June 2024 Uganda NDA human-medicine register snapshot."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.db import transaction

from interoperability.models import TerminologyConcept

SYSTEM = "https://www.nda.or.ug/drug-register/"
SOURCE = "https://www.nda.or.ug/wp-content/uploads/2024/06/NATIONAL-DRUG-REGISTER-OF-UGANDA-HUMAN-MEDICINES-JUNE-2024.pdf"
VERSION = "2024-06"
CATEGORY = "registered_medicine_reference"


@transaction.atomic
def import_register():
    rows = json.loads(Path(__file__).with_name("uganda_nda_human_medicines_2024_06.json").read_text())
    if len(rows) != 50 or len({row["code"] for row in rows}) != len(rows):
        raise ValueError("Expected 50 distinct registration numbers.")
    for row in rows:
        TerminologyConcept.objects.update_or_create(system=SYSTEM, version=VERSION, code=row["code"], defaults={
            "category": CATEGORY,
            "display": row["product"],
            "aliases": [row["ingredient"]],
            "metadata": {
                "ingredient": row["ingredient"], "strength": row["strength"],
                "dosage_form": row["form"], "pack_size": row["pack"], "source_url": SOURCE,
            },
            "active": True,
        })
    print(f"Verified {TerminologyConcept.objects.filter(system=SYSTEM, version=VERSION, category=CATEGORY).count()} reference records.")


if __name__ == "__main__":
    database = settings.DATABASES["default"]
    expected = Path(__file__).resolve().parents[1] / "db.sqlite3"
    if not settings.DEBUG or database["ENGINE"] != "django.db.backends.sqlite3" or Path(database["NAME"]).resolve() != expected:
        raise SystemExit("This command imports into the local development SQLite database.")
    import_register()
