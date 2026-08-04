from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("communication", "0002_notification_delivery_preferences_templates")]

    operations = [
        migrations.AddField(model_name="notificationpreference", name="whatsapp_enabled", field=models.BooleanField(default=False)),
        migrations.AlterField(model_name="notificationdelivery", name="channel", field=models.CharField(choices=[("in_app", "In application"), ("email", "Email"), ("sms", "SMS"), ("push", "Push notification"), ("whatsapp", "WhatsApp")], max_length=20)),
    ]
