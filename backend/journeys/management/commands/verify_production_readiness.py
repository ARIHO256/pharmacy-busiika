import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from journeys.models import ReleaseAcceptance


class Command(BaseCommand):
    help = "Fail unless every formal release-acceptance gate and production configuration check is current."

    def add_arguments(self, parser):
        parser.add_argument("--release", required=True, dest="release_version")
        parser.add_argument("--environment", default="production")
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--allow-non-postgres", action="store_true")

    def handle(self, *args, **options):
        release_version = options["release_version"]
        environment = options["environment"]
        rows = ReleaseAcceptance.objects.filter(
            release_version=release_version,
            environment=environment,
        ).select_related("reviewer")
        by_type = {row.acceptance_type: row for row in rows}
        required = [choice[0] for choice in ReleaseAcceptance.Type.choices]
        gates = []
        for gate_type in required:
            row = by_type.get(gate_type)
            gates.append({
                "type": gate_type,
                "status": row.status if row else "missing",
                "accepted": bool(row and row.is_currently_accepted),
                "reviewer": row.reviewer_name if row else "",
                "signed_at": row.signed_at.isoformat() if row and row.signed_at else None,
                "evidence_hash": row.evidence_hash if row else "",
            })

        database_engine = settings.DATABASES["default"].get("ENGINE", "")
        configuration = {
            "debug_disabled": not settings.DEBUG,
            "postgresql": "postgresql" in database_engine,
            "secure_secret_key": len(str(settings.SECRET_KEY)) >= 32 and "change-me" not in str(settings.SECRET_KEY).lower(),
            "allowed_hosts_configured": bool(settings.ALLOWED_HOSTS) and "*" not in settings.ALLOWED_HOSTS,
            "mock_payments_disabled": not bool(getattr(settings, "ALLOW_MOCK_PAYMENTS", False)),
            "https_redirect": bool(getattr(settings, "SECURE_SSL_REDIRECT", False)),
            "secure_session_cookie": bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
            "secure_csrf_cookie": bool(getattr(settings, "CSRF_COOKIE_SECURE", False)),
            "external_provider_mode": str(os.getenv("HEALTHPILOT_PROVIDER_MODE", "sandbox")).lower() in {"sandbox", "production"},
        }
        if options["allow_non_postgres"]:
            configuration["postgresql"] = True

        result = {
            "release_version": release_version,
            "environment": environment,
            "checked_at": timezone.now().isoformat(),
            "acceptance_gates": gates,
            "configuration": configuration,
        }
        result["ready"] = all(item["accepted"] for item in gates) and all(configuration.values())

        if options["as_json"]:
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING(f"Production readiness: {release_version} ({environment})"))
            for item in gates:
                marker = self.style.SUCCESS("PASS") if item["accepted"] else self.style.ERROR("BLOCK")
                self.stdout.write(f"  {marker} {item['type']}: {item['status']}")
            for name, passed in configuration.items():
                marker = self.style.SUCCESS("PASS") if passed else self.style.ERROR("BLOCK")
                self.stdout.write(f"  {marker} configuration.{name}")

        if not result["ready"]:
            raise CommandError("Production promotion is blocked. Resolve every acceptance and configuration gate.")
        self.stdout.write(self.style.SUCCESS("All production-readiness gates are current."))
