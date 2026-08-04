from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("registry", "0004_organization_rejected_status"), ("accounts", "0008_provider_license_dates")]
    operations = [
        migrations.AddField(model_name="organization", name="license_issued_on", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="organization", name="license_expires_on", field=models.DateField(blank=True, null=True)),
    ]
