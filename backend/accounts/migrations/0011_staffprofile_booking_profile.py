from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_patient_relationships")]

    operations = [
        migrations.AddField(model_name="staffprofile", name="specialty", field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="staffprofile", name="workplace", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="staffprofile", name="experience_years", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="staffprofile", name="consultation_fee", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="staffprofile", name="offers_appointments", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="staffprofile", name="average_rating", field=models.DecimalField(decimal_places=2, default=0, max_digits=3)),
        migrations.AddIndex(model_name="staffprofile", index=models.Index(fields=["offers_appointments", "status"], name="accounts_st_offers__84a3d0_idx")),
    ]
