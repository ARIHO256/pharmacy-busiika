"""Reconcile the store catalog with operations inventory.

For every Medicine sold by an organization-owned pharmacy, ensure a matching
operations InventoryItem + batch exists, link them, and align on-hand quantity
to the store stock (the commercial truth), leaving an adjustment movement for
the audit trail. Idempotent.

Run from backend/:
    .venv/bin/python reconcile_inventory.py
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import ProviderProfile  # noqa: E402
from operations.models import InventoryBatch, InventoryItem, StockMovement  # noqa: E402
from registry.models import Organization  # noqa: E402
from services.models import Medicine  # noqa: E402


@transaction.atomic
def main():
    orgs = {org.owner_id: org for org in Organization.objects.filter(organization_type="pharmacy", active=True)}
    # Fall back to matching through the provider profile's organization name.
    linked = created_items = adjusted = 0
    for medicine in Medicine.objects.select_related("pharmacy").all():
        org = orgs.get(medicine.pharmacy_id)
        if org is None:
            profile = ProviderProfile.objects.filter(user_id=medicine.pharmacy_id).first()
            if profile:
                org = Organization.objects.filter(legal_name=profile.org_name).first()
        if org is None:
            continue

        item = medicine.inventory_item
        if item is None:
            item, was_created = InventoryItem.objects.get_or_create(
                organization=org,
                sku=f"STORE-{medicine.id:05d}",
                defaults={
                    "name": medicine.name,
                    "category": "Pharmacy retail",
                    "unit": "pack",
                    "reorder_level": 20,
                },
            )
            created_items += was_created
            medicine.inventory_item = item
            medicine.save(update_fields=["inventory_item"])
            linked += 1

        on_hand = item.quantity_on_hand
        if on_hand != medicine.stock:
            batch = item.batches.filter(recalled=False).order_by("expiry_date", "received_at").first()
            if batch is None:
                batch = InventoryBatch.objects.create(
                    item=item,
                    batch_number=f"STORE-{medicine.id:05d}-A",
                    quantity_received=0,
                    quantity_available=0,
                    unit_cost=0,
                    selling_price=medicine.price,
                    storage_location="Retail shelf",
                )
            delta = medicine.stock - batch.quantity_available
            batch.quantity_available = medicine.stock
            batch.quantity_received = max(batch.quantity_received, medicine.stock)
            batch.selling_price = medicine.price
            batch.save(update_fields=["quantity_available", "quantity_received", "selling_price"])
            StockMovement.objects.create(
                batch=batch,
                movement_type=StockMovement.Type.ADJUSTMENT,
                quantity=delta,
                balance_after=batch.quantity_available,
                reason="Store/inventory reconciliation: align on-hand with store stock.",
                reference="store-reconcile",
            )
            adjusted += 1

    print(f"Reconciliation complete: {linked} medicines linked, {created_items} inventory items created, {adjusted} batches adjusted")


if __name__ == "__main__":
    main()
