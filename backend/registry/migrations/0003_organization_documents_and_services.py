from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0002_backfill_existing_registry_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="license_document",
            field=models.FileField(blank=True, null=True, upload_to="registry/organizations/"),
        ),
        migrations.AddField(
            model_name="organization",
            name="services_description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
