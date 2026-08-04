from django.db import migrations


def backfill_registry(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    ProviderProfile = apps.get_model("accounts", "ProviderProfile")
    Appointment = apps.get_model("appointments", "Appointment")
    Organization = apps.get_model("registry", "Organization")
    CareRelationship = apps.get_model("registry", "CareRelationship")

    type_map = {
        "pharmacy": "pharmacy",
        "lab": "laboratory",
        "hospital": "hospital",
        "insurance": "insurer",
    }
    status_map = {
        "pending": "pending",
        "verified": "verified",
        "suspended": "suspended",
    }

    for profile in ProviderProfile.objects.select_related("user").all().iterator():
        user = profile.user
        organization_type = type_map.get(user.role)
        if not organization_type:
            continue
        name = (profile.org_name or f"{user.first_name} {user.last_name}".strip() or user.email).strip()
        Organization.objects.get_or_create(
            owner_id=user.id,
            organization_type=organization_type,
            legal_name=name,
            defaults={
                "trading_name": profile.org_name or "",
                "license_number": profile.license_number or "",
                "status": status_map.get(profile.status, "pending"),
                "contact_email": user.email,
                "phone": user.phone or "",
                "address": profile.address or "",
                "country_code": "UG",
                "active": profile.status != "suspended",
            },
        )

    for appointment in Appointment.objects.all().iterator():
        CareRelationship.objects.get_or_create(
            patient_id=appointment.patient_id,
            practitioner_id=appointment.doctor_id,
            appointment_id=appointment.id,
            defaults={
                "relationship_type": "treatment",
                "purpose": "treatment",
                "status": "ended" if appointment.status == "cancelled" else "active",
                "created_by_id": appointment.patient_id,
            },
        )


def reverse_backfill(apps, schema_editor):
    # Registry data may have been edited after migration; destructive rollback is unsafe.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0001_initial"),
        ("accounts", "0002_doctorprofile_patientprofile_providerprofile"),
        ("appointments", "0002_appointmentstatushistory_and_more"),
    ]

    operations = [migrations.RunPython(backfill_registry, reverse_backfill)]
