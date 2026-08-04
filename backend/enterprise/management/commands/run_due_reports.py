from django.core.management.base import BaseCommand

from enterprise.tasks import dispatch_due_report_schedules


class Command(BaseCommand):
    help = "Dispatch report schedules that are due."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        count = dispatch_due_report_schedules.run(limit=max(1, options["limit"]))
        self.stdout.write(self.style.SUCCESS(f"Dispatched {count} scheduled report(s)."))
