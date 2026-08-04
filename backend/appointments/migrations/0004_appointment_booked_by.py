from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_patient_relationships"),
        ("appointments", "0003_backfill_status_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="booked_by",
            field=models.ForeignKey(blank=True, help_text="Patient or authorized caregiver who created the booking.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="booked_appointments", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunSQL(
            sql="UPDATE appointments_appointment SET booked_by_id = patient_id WHERE booked_by_id IS NULL",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
