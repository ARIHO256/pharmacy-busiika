import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0002_labresult_criticalresultacknowledgement_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="laborder",
            name="status",
            field=models.CharField(choices=[("booked", "Ordered"), ("awaiting_payment", "Awaiting payment"), ("ready_for_collection", "Ready for collection"), ("sample_collected", "Sample collected"), ("sample_received", "Sample received"), ("processing", "In progress"), ("preliminary", "Preliminary"), ("awaiting_validation", "Awaiting validation"), ("validated", "Validated"), ("completed", "Released"), ("amended", "Amended"), ("cancelled", "Cancelled"), ("rejected", "Rejected specimen")], default="booked", max_length=24),
        ),
        migrations.AddField(model_name="laborder", name="clinical_indication", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="laborder", name="collection_notes", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="laborder", name="collected_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="laborder", name="priority", field=models.CharField(choices=[("routine", "Routine"), ("urgent", "Urgent"), ("stat", "STAT / emergency")], default="routine", max_length=20)),
        migrations.AddField(model_name="laborder", name="provisional_diagnosis", field=models.CharField(blank=True, default="", max_length=250)),
        migrations.AddField(model_name="laborder", name="received_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="laborder", name="referring_facility", field=models.CharField(blank=True, default="", max_length=220)),
        migrations.AddField(model_name="laborder", name="rejection_reason", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="laborder", name="released_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="laborder", name="result_released", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="laborder", name="specimen_id", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="laborder", name="specimen_type", field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="laborder", name="updated_at", field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name="laborder", name="collected_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="collected_lab_specimens", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="laborder", name="referring_doctor", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="referred_lab_orders", to=settings.AUTH_USER_MODEL)),
        migrations.AddIndex(model_name="laborder", index=models.Index(fields=["lab", "status", "created_at"], name="svc_lab_lab_stat_time_idx")),
        migrations.AddIndex(model_name="laborder", index=models.Index(fields=["patient", "created_at"], name="svc_lab_patient_time_idx")),
        migrations.AddIndex(model_name="laborder", index=models.Index(fields=["specimen_id"], name="svc_lab_specimen_idx")),
        migrations.AlterField(
            model_name="labresult",
            name="status",
            field=models.CharField(choices=[("preliminary", "Preliminary"), ("final", "Final"), ("amended", "Amended"), ("corrected", "Corrected"), ("cancelled", "Cancelled")], default="preliminary", max_length=20),
        ),
        migrations.AddField(model_name="labresult", name="amendment_reason", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="labresult", name="released_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="labresult", name="entered_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="entered_lab_results", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="labresult", name="released_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="released_lab_results", to=settings.AUTH_USER_MODEL)),
    ]
