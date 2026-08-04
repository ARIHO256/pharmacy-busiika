from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_patient_relationships"),
        ("clinical", "0001_initial"),
        ("registry", "0005_organization_license_dates"),
    ]

    operations = [
        migrations.AddField(model_name="referral", name="target_provider", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="incoming_referrals", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="referral", name="target_organization", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="referrals", to="registry.organization")),
        migrations.AddField(model_name="referral", name="accepted_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accepted_referrals", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="referral", name="accepted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="referral", name="completed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="referral", name="outcome_summary", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="referral", name="decline_reason", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="referral", name="feedback_acknowledged_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddIndex(model_name="referral", index=models.Index(fields=["target_provider", "status", "priority"], name="clinical_re_target__18da66_idx")),
        migrations.AddIndex(model_name="referral", index=models.Index(fields=["referring_provider", "status"], name="clinical_re_referri_0b503d_idx")),
        migrations.AddIndex(model_name="referral", index=models.Index(fields=["target_organization", "status"], name="clinical_re_target__38585a_idx")),
        migrations.CreateModel(
            name="ReferralStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_status", models.CharField(blank=True, default="", max_length=20)),
                ("to_status", models.CharField(choices=[("draft", "Draft"), ("sent", "Sent"), ("accepted", "Accepted"), ("in_progress", "In progress"), ("completed", "Completed"), ("declined", "Declined"), ("cancelled", "Cancelled")], max_length=20)),
                ("reason", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="referral_status_actions", to=settings.AUTH_USER_MODEL)),
                ("referral", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_history", to="clinical.referral")),
            ],
            options={"ordering": ["created_at"], "indexes": [models.Index(fields=["referral", "created_at"], name="clinical_re_referra_dde33e_idx")]},
        ),
    ]
