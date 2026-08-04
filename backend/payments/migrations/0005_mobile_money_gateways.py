from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payments", "0004_webhooks_adjustments_refunds")]
    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="gateway",
            field=models.CharField(
                choices=[
                    ("mock", "Mock"), ("cash", "Cash"), ("mobile_money", "Mobile money"),
                    ("card", "Card"), ("bank", "Bank transfer"), ("insurance", "Insurance"),
                    ("flutterwave", "Flutterwave"), ("paystack", "Paystack"),
                    ("mtn_momo", "MTN Mobile Money"), ("airtel_money", "Airtel Money"),
                ],
                default="mock",
                max_length=24,
            ),
        ),
    ]
