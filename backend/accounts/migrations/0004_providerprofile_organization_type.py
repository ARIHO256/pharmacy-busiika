from django.db import migrations, models


def backfill_organization_types(apps, schema_editor):
    ProviderProfile = apps.get_model("accounts", "ProviderProfile")
    role_map = {
        "hospital": "hospital",
        "pharmacy": "pharmacy",
        "lab": "laboratory",
        "insurance": "insurer",
    }
    for profile in ProviderProfile.objects.select_related("user").all().iterator():
        organization_type = role_map.get(profile.user.role, "hospital")
        ProviderProfile.objects.filter(pk=profile.pk).update(
            organization_type=organization_type
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_role_profiles_and_staff")]

    operations = [
        migrations.AddField(
            model_name="providerprofile",
            name="organization_type",
            field=models.CharField(
                choices=[
                    ("hospital", "Hospital"),
                    ("clinic", "Clinic"),
                    ("pharmacy", "Pharmacy"),
                    ("laboratory", "Laboratory"),
                    ("insurer", "Insurance provider"),
                ],
                default="hospital",
                max_length=30,
            ),
        ),
        migrations.RunPython(backfill_organization_types, migrations.RunPython.noop),
    ]
