from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_provider_license_dates")]

    operations = [
        migrations.AddField(
            model_name="doctorprofile",
            name="license_issued_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="license_issued_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
