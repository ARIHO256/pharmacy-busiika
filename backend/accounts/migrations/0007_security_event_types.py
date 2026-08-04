from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_expand_user_role_choices")]
    operations = [
        migrations.AlterField(
            model_name="securityevent",
            name="event_type",
            field=models.CharField(choices=[
                ("login_success", "Login success"),
                ("login_failed", "Login failed"),
                ("account_locked", "Account locked"),
                ("password_changed", "Password changed"),
                ("password_reset", "Password reset"),
                ("email_verified", "Email verified"),
                ("phone_verified", "Phone verified"),
                ("session_revoked", "Session revoked"),
                ("logout", "Logout"),
                ("mfa_enabled", "MFA enabled"),
                ("mfa_disabled", "MFA disabled"),
                ("mfa_challenge", "MFA challenge"),
            ], max_length=32),
        ),
    ]
