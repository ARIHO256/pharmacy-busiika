"""Keep store medicine stock in sync with operations inventory.

The store sells from ``services.Medicine.stock`` while pharmacy staff manage
stock through ``operations.InventoryItem`` batches. Whenever a stock movement
is recorded, linked store listings are realigned to the item's on-hand
quantity so every page shows the same number.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="operations.StockMovement")
def sync_store_stock(sender, instance, **kwargs):
    from .models import Medicine

    item = instance.batch.item
    Medicine.objects.filter(inventory_item=item).update(stock=item.quantity_on_hand)
