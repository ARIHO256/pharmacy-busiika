from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("journeys", "0002_operational_workflows"),
        ("registry", "0005_organization_license_dates"),
        ("workforce", "0002_granular_permissions"),
        ("appointments", "0004_appointment_booked_by"),
        ("operations", "0002_care_pathways_workforce_quality"),
        ("payments", "0005_mobile_money_gateways"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OperationalAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("page_slug", models.SlugField(db_index=True, max_length=100)),
                ("domain", models.CharField(db_index=True, max_length=80)),
                ("operation_code", models.CharField(db_index=True, max_length=100)),
                ("state", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted"), ("under_review", "Under review"), ("approved", "Approved"), ("executed", "Executed"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("reversed", "Reversed"), ("failed", "Failed")], db_index=True, default="submitted", max_length=24)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("effect_log", models.JSONField(blank=True, default=list)),
                ("effect_reference_type", models.CharField(blank=True, default="", max_length=100)),
                ("effect_reference_id", models.CharField(blank=True, default="", max_length=100)),
                ("requires_approval", models.BooleanField(default=False)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("executed_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("admission", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operational_actions", to="operations.admission")),
                ("appointment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operational_actions", to="appointments.appointment")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_operational_actions", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_operational_actions", to=settings.AUTH_USER_MODEL)),
                ("department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operational_actions", to="workforce.department")),
                ("executed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="executed_operational_actions", to=settings.AUTH_USER_MODEL)),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operational_actions", to="payments.invoice")),
                ("location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operational_actions", to="registry.organizationlocation")),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operational_actions", to="registry.organization")),
                ("patient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="patient_operational_actions", to=settings.AUTH_USER_MODEL)),
                ("subject_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="subject_operational_actions", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_operational_actions", to=settings.AUTH_USER_MODEL)),
                ("workflow_case", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="operational_action", to="journeys.workflowcase")),
            ],
            options={"ordering": ["-updated_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="ReleaseAcceptance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("release_version", models.CharField(db_index=True, max_length=80)),
                ("environment", models.CharField(db_index=True, default="production", max_length=40)),
                ("acceptance_type", models.CharField(choices=[("doctor_workflow", "Doctor workflow acceptance"), ("nursing_workflow", "Nursing and midwifery acceptance"), ("laboratory_workflow", "Laboratory acceptance"), ("pharmacy_workflow", "Pharmacy acceptance"), ("finance_workflow", "Finance acceptance"), ("records_workflow", "Medical records acceptance"), ("admin_workflow", "Administrator acceptance"), ("privacy_legal", "Privacy and legal approval"), ("clinical_safety", "Clinical safety approval"), ("security", "Security approval"), ("backup_restore", "Backup and restore evidence"), ("disaster_recovery", "Disaster recovery approval")], db_index=True, max_length=40)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("expired", "Expired")], db_index=True, default="pending", max_length=20)),
                ("reviewer_name", models.CharField(max_length=220)),
                ("reviewer_title", models.CharField(blank=True, default="", max_length=180)),
                ("reviewer_email", models.EmailField(blank=True, default="", max_length=254)),
                ("statement", models.TextField()),
                ("evidence", models.FileField(blank=True, null=True, upload_to="release-acceptance/%Y/%m/")),
                ("evidence_hash", models.CharField(blank=True, default="", max_length=128)),
                ("signed_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reviewer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="release_acceptances", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["acceptance_type", "-updated_at"]},
        ),
        migrations.AddIndex(
            model_name="operationalaction",
            index=models.Index(fields=["page_slug", "state"], name="journey_op_page_state"),
        ),
        migrations.AddIndex(
            model_name="operationalaction",
            index=models.Index(fields=["organization", "domain", "state"], name="journey_op_org_domain"),
        ),
        migrations.AddIndex(
            model_name="operationalaction",
            index=models.Index(fields=["patient", "page_slug"], name="journey_op_patient"),
        ),
        migrations.AddConstraint(
            model_name="releaseacceptance",
            constraint=models.UniqueConstraint(fields=("release_version", "environment", "acceptance_type"), name="journey_unique_release_acceptance"),
        ),
    ]
