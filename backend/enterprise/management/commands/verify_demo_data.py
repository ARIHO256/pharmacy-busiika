from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from enterprise.models import EnterpriseRecord, RoleContext
from enterprise.schemas import RECORD_SCHEMAS
from registry.models import Organization
from enterprise.demo_seed import ROLE_EMAIL as DEMO_ROLE_ACCOUNTS


class Command(BaseCommand):
    help = "Verify that the seeded demonstration database covers every role and enterprise workflow."

    def handle(self, *args, **options):
        User = get_user_model()
        errors = []

        for role, email in DEMO_ROLE_ACCOUNTS.items():
            user = User.objects.filter(email=email).first()
            if user is None:
                errors.append(f"missing account {role}: {email}")
                continue
            if user.role != role:
                errors.append(f"{email} has role {user.role!r}, expected {role!r}")
            if not user.is_active:
                errors.append(f"{email} is inactive")
            if not RoleContext.objects.filter(user=user, role_code=role, active=True).exists():
                errors.append(f"{email} has no active {role} role context")

        missing_workflows = [
            record_type
            for record_type in RECORD_SCHEMAS
            if not EnterpriseRecord.objects.filter(record_type=record_type).exists()
        ]
        if missing_workflows:
            errors.append("missing enterprise demo records: " + ", ".join(missing_workflows))

        required_org_types = {"hospital", "pharmacy", "laboratory", "insurer"}
        existing_org_types = set(Organization.objects.filter(active=True).values_list("organization_type", flat=True))
        missing_orgs = sorted(required_org_types - existing_org_types)
        if missing_orgs:
            errors.append("missing active organization types: " + ", ".join(missing_orgs))

        if errors:
            raise CommandError("Demo verification failed:\n- " + "\n- ".join(errors))

        self.stdout.write(self.style.SUCCESS(
            f"Demo verified: {len(DEMO_ROLE_ACCOUNTS)} roles, "
            f"{len(RECORD_SCHEMAS)} workflow types, "
            f"{Organization.objects.filter(active=True).count()} active organizations."
        ))
