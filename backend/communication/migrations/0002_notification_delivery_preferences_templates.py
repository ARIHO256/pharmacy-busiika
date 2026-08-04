import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import communication.models


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="action_url",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddField(
            model_name="notification",
            name="channels",
            field=models.JSONField(blank=True, default=communication.models.default_notification_channels),
        ),
        migrations.AddField(
            model_name="notification",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="notification",
            name="priority",
            field=models.CharField(
                choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("critical", "Critical")],
                default="normal",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "is_read", "created_at"], name="comm_notif_user_read_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["kind", "created_at"], name="comm_notif_kind_time_idx"),
        ),
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("in_app_enabled", models.BooleanField(default=True)),
                ("email_enabled", models.BooleanField(default=True)),
                ("sms_enabled", models.BooleanField(default=False)),
                ("push_enabled", models.BooleanField(default=False)),
                ("appointment_reminders", models.BooleanField(default=True)),
                ("clinical_updates", models.BooleanField(default=True)),
                ("payment_updates", models.BooleanField(default=True)),
                ("marketing_updates", models.BooleanField(default=False)),
                ("quiet_hours_start", models.TimeField(blank=True, null=True)),
                ("quiet_hours_end", models.TimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="notification_preferences", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="NotificationTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=100, unique=True)),
                ("title_template", models.CharField(max_length=220)),
                ("body_template", models.TextField()),
                ("kind", models.CharField(default="general", max_length=50)),
                ("default_priority", models.CharField(choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("critical", "Critical")], default="normal", max_length=20)),
                ("default_channels", models.JSONField(blank=True, default=communication.models.default_notification_channels)),
                ("active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("in_app", "In application"), ("email", "Email"), ("sms", "SMS"), ("push", "Push notification")], max_length=20)),
                ("recipient", models.CharField(blank=True, default="", max_length=220)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("sent", "Sent"), ("delivered", "Delivered"), ("failed", "Failed"), ("skipped", "Skipped")], default="pending", max_length=20)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("provider_reference", models.CharField(blank=True, default="", max_length=160)),
                ("last_error", models.TextField(blank=True, default="")),
                ("last_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="communication.notification")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="notificationdelivery",
            constraint=models.UniqueConstraint(fields=("notification", "channel"), name="unique_notification_delivery_channel"),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(fields=["channel", "status", "created_at"], name="comm_deliv_chan_stat_idx"),
        ),
    ]
