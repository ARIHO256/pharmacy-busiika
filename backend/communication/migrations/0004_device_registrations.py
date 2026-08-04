from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("communication", "0003_whatsapp_delivery")]

    operations = [
        migrations.CreateModel(
            name="DeviceRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("web", "Web"), ("android", "Android"), ("ios", "iOS")], max_length=20)),
                ("token", models.CharField(max_length=500, unique=True)),
                ("device_name", models.CharField(blank=True, default="", max_length=160)),
                ("active", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_devices", to="accounts.user")),
            ],
            options={"ordering": ["-last_seen_at"]},
        ),
        migrations.AddIndex(model_name="deviceregistration", index=models.Index(fields=["user", "active", "last_seen_at"], name="communicati_user_id_4bd1ad_idx")),
    ]
