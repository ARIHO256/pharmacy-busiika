import json

from django.core.management.base import BaseCommand

from enterprise.models import NotificationProvider, PACSNode
from enterprise.services import pacs_health_check, provider_health_check


class Command(BaseCommand):
    help = "Check notification providers and PACS nodes, then persist their health status."

    def handle(self, *args, **options):
        results = {
            "notifications": [provider_health_check(row) for row in NotificationProvider.objects.filter(active=True)],
            "pacs": [pacs_health_check(row) for row in PACSNode.objects.filter(active=True)],
        }
        self.stdout.write(json.dumps(results, default=str, indent=2))
