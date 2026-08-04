import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("payments", "0003_billing_receipts_and_cashier_shifts")]

    operations = [
        migrations.CreateModel(
            name="PaymentWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gateway", models.CharField(max_length=24)),
                ("event_id", models.CharField(max_length=180)),
                ("event_type", models.CharField(blank=True, default="", max_length=80)),
                ("signature_valid", models.BooleanField(default=False)),
                ("payload", models.JSONField(default=dict)),
                ("outcome", models.CharField(blank=True, default="", max_length=40)),
                ("error", models.TextField(blank=True, default="")),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-received_at"]},
        ),
        migrations.CreateModel(
            name="InvoiceAdjustment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=40, unique=True)),
                ("adjustment_type", models.CharField(choices=[("credit", "Credit note"), ("debit", "Debit note"), ("discount", "Discount"), ("write_off", "Write-off")], max_length=20)),
                ("amount", models.PositiveBigIntegerField()),
                ("reason", models.TextField()),
                ("status", models.CharField(choices=[("requested", "Requested"), ("approved", "Approved"), ("rejected", "Rejected"), ("applied", "Applied")], default="requested", max_length=20)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_invoice_adjustments", to=settings.AUTH_USER_MODEL)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="adjustments", to="payments.invoice")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_invoice_adjustments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="RefundRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=40, unique=True)),
                ("amount", models.PositiveBigIntegerField()),
                ("reason", models.TextField()),
                ("status", models.CharField(choices=[("requested", "Requested"), ("approved", "Approved"), ("processing", "Processing"), ("completed", "Completed"), ("rejected", "Rejected"), ("failed", "Failed")], default="requested", max_length=20)),
                ("gateway_reference", models.CharField(blank=True, default="", max_length=180)),
                ("error", models.TextField(blank=True, default="")),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_refunds", to=settings.AUTH_USER_MODEL)),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refund_requests", to="payments.paymenttransaction")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_refunds", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="paymentwebhookevent", constraint=models.UniqueConstraint(fields=("gateway", "event_id"), name="unique_gateway_webhook_event")),
        migrations.AddIndex(model_name="paymentwebhookevent", index=models.Index(fields=["gateway", "received_at"], name="payments_pa_gateway_60c705_idx")),
    ]
