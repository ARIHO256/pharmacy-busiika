from django.core.management.base import BaseCommand
from operations.tasks import deliver_events


class Command(BaseCommand):
    help = "Deliver due outbox events using the configured signed webhook transport."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        result = deliver_events(limit=options["limit"])
        self.stdout.write(f"sent={result['sent']} failed={result['failed']}")
