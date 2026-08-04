from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_security_event_types")]
    operations = [
        migrations.AddField(model_name="providerprofile", name="license_issuer", field=models.CharField(blank=True, default="", max_length=180)),
        migrations.AddField(model_name="providerprofile", name="license_issued_on", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="providerprofile", name="license_expires_on", field=models.DateField(blank=True, null=True)),
    ]
