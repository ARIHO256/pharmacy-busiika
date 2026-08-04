from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import governance.models


class Migration(migrations.Migration):
    dependencies = [
        ("governance", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PrivilegedAccessGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("purpose", models.CharField(max_length=120)),
                ("reason", models.TextField()),
                ("scopes", models.JSONField(blank=True, default=list)),
                ("read_only", models.BooleanField(default=True)),
                ("status", models.CharField(choices=[("pending", "Pending approval"), ("active", "Active"), ("rejected", "Rejected"), ("revoked", "Revoked"), ("expired", "Expired"), ("reviewed", "Reviewed")], default="pending", max_length=20)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("mfa_verified_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(default=governance.models.default_privileged_access_expiry)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_notes", models.TextField(blank=True, default="")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_privileged_access_grants", to=settings.AUTH_USER_MODEL)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="privileged_admin_accesses", to=settings.AUTH_USER_MODEL)),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="privileged_access_requests", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_privileged_access_grants", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-requested_at"],
                "indexes": [
                    models.Index(fields=["requester", "patient", "status"], name="gov_priv_actor_patient"),
                    models.Index(fields=["expires_at", "status"], name="gov_priv_expiry_status"),
                ],
            },
        )
    ]
