# Generated manually for the full-scale HealthPilot upgrade.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_professional_license_issue_dates"),
    ]

    operations = [
        migrations.CreateModel(
            name="PatientRelationship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("relationship", models.CharField(choices=[("parent", "Parent"), ("guardian", "Legal guardian"), ("spouse", "Spouse"), ("child", "Adult child"), ("sibling", "Sibling"), ("caregiver", "Caregiver"), ("legal_representative", "Legal representative"), ("other", "Other")], max_length=32)),
                ("status", models.CharField(choices=[("pending", "Pending verification"), ("active", "Active"), ("suspended", "Suspended"), ("revoked", "Revoked"), ("expired", "Expired")], default="pending", max_length=20)),
                ("can_book", models.BooleanField(default=True)),
                ("can_view_records", models.BooleanField(default=True)),
                ("can_manage_billing", models.BooleanField(default=True)),
                ("can_receive_notifications", models.BooleanField(default=True)),
                ("authority_document", models.FileField(blank=True, null=True, upload_to="patients/caregiver-authority/")),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("caregiver", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="managed_patient_relationships", to=settings.AUTH_USER_MODEL)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="caregiver_relationships", to=settings.AUTH_USER_MODEL)),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="verified_patient_relationships", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["patient__first_name", "patient__last_name", "id"],
                "indexes": [models.Index(fields=["caregiver", "status"], name="accounts_pa_caregiv_e0a130_idx"), models.Index(fields=["patient", "status"], name="accounts_pa_patient_1adb93_idx")],
                "constraints": [models.UniqueConstraint(fields=("caregiver", "patient"), name="unique_patient_caregiver_relationship"), models.CheckConstraint(condition=models.Q(("caregiver", models.F("patient")), _negated=True), name="patient_caregiver_cannot_be_same_user")],
            },
        ),
    ]
