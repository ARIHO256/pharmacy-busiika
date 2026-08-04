from django.core.management.base import BaseCommand, CommandError

from enterprise.services import scan_duplicate_patients


class Command(BaseCommand):
    help = "Run the master-patient-index duplicate detector."

    def add_arguments(self, parser):
        parser.add_argument("--min-score", type=float, default=70)

    def handle(self, *args, **options):
        score = options["min_score"]
        if not 0 <= score <= 100:
            raise CommandError("--min-score must be between 0 and 100")
        result = scan_duplicate_patients(min_score=score)
        self.stdout.write(self.style.SUCCESS(str(result)))
