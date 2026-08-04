import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_providerprofile_organization_type")]

    operations = [
        migrations.AddField(model_name="user", name="email_verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="user", name="phone_verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="user", name="mfa_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="user", name="failed_login_attempts", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="user", name="locked_until", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="user", name="last_password_change_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name="OneTimeToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("purpose", models.CharField(choices=[("email_verification", "Email verification"), ("password_reset", "Password reset"), ("mfa_login", "MFA login"), ("phone_verification", "Phone verification")], max_length=32)),
                ("token_hash", models.CharField(max_length=128)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("request_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="one_time_tokens", to="accounts.user")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SecurityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("login_success", "Login success"), ("login_failed", "Login failed"), ("account_locked", "Account locked"), ("password_changed", "Password changed"), ("password_reset", "Password reset"), ("email_verified", "Email verified"), ("mfa_enabled", "MFA enabled"), ("mfa_disabled", "MFA disabled"), ("mfa_challenge", "MFA challenge")], max_length=32)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("request_id", models.CharField(blank=True, default="", max_length=100)),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_events", to="accounts.user")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="onetimetoken", index=models.Index(fields=["public_id", "purpose"], name="accounts_on_public__fe1819_idx")),
        migrations.AddIndex(model_name="onetimetoken", index=models.Index(fields=["user", "purpose", "expires_at"], name="accounts_on_user_id_4cdf7b_idx")),
        migrations.AddIndex(model_name="securityevent", index=models.Index(fields=["user", "event_type", "created_at"], name="accounts_se_user_id_a321bf_idx")),
    ]
