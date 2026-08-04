from django.core.management.base import BaseCommand

from enterprise.demo_seed import seed_enterprise_demo


class Command(BaseCommand):
    help = "Populate every enterprise workflow, portal and integration area with idempotent demonstration data."

    def handle(self, *args, **options):
        result = seed_enterprise_demo()
        for key, value in result.items():
            self.stdout.write(f"{key}: {value}")
        self.stdout.write(self.style.SUCCESS("Enterprise demonstration data is ready."))
