from django.core.management.base import BaseCommand

from accounts.models import ProviderProfile
from registry.services import sync_provider_organization


class Command(BaseCommand):
    help = "Create or update canonical registry organizations from provider profiles."

    def handle(self, *args, **options):
        synced = 0
        failed = 0
        for profile in ProviderProfile.objects.select_related("user").iterator():
            try:
                sync_provider_organization(profile.user, profile)
                synced += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"{profile.user.email}: {exc}")
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"Provider registry synchronization complete: {synced} synced, {failed} failed."
            )
        )
