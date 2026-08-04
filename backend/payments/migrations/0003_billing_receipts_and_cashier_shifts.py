import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_journalentry_ledgeraccount_posting"),
        ("registry", "0004_organization_rejected_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="number",
            field=models.CharField(blank=True, max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="amount",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="status",
            field=models.CharField(choices=[("draft", "Draft"), ("pending", "Pending"), ("partially_paid", "Partially paid"), ("paid", "Paid"), ("failed", "Failed"), ("refunded", "Refunded"), ("void", "Void")], default="pending", max_length=24),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="gateway",
            field=models.CharField(choices=[("mock", "Mock"), ("cash", "Cash"), ("mobile_money", "Mobile money"), ("card", "Card"), ("bank", "Bank transfer"), ("insurance", "Insurance"), ("flutterwave", "Flutterwave"), ("paystack", "Paystack")], default="mock", max_length=24),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="gateway_ref",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(model_name="invoice", name="currency", field=models.CharField(default="UGX", max_length=3)),
        migrations.AddField(model_name="invoice", name="discount_amount", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="invoice", name="due_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="invoice", name="notes", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="invoice", name="tax_amount", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="invoice", name="updated_at", field=models.DateTimeField(auto_now=True)),
        migrations.AddField(
            model_name="invoice",
            name="issued_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_invoices", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="invoice",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="registry.organization"),
        ),
        migrations.AddIndex(model_name="invoice", index=models.Index(fields=["organization", "status", "created_at"], name="pay_inv_org_stat_time_idx")),
        migrations.AddIndex(model_name="invoice", index=models.Index(fields=["patient", "status"], name="pay_inv_patient_stat_idx")),
        migrations.CreateModel(
            name="InvoiceItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(blank=True, default="", max_length=80)),
                ("description", models.CharField(max_length=240)),
                ("quantity", models.DecimalField(decimal_places=2, default=1, max_digits=10, validators=[django.core.validators.MinValueValidator(0.01)])),
                ("unit_price", models.PositiveBigIntegerField()),
                ("discount_amount", models.PositiveBigIntegerField(default=0)),
                ("line_total", models.PositiveBigIntegerField(default=0)),
                ("service_type", models.CharField(blank=True, default="", max_length=60)),
                ("source_id", models.CharField(blank=True, default="", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="payments.invoice")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=30, unique=True)),
                ("amount", models.PositiveBigIntegerField()),
                ("method", models.CharField(choices=[("cash", "Cash"), ("mobile_money", "Mobile money"), ("card", "Card"), ("bank", "Bank transfer"), ("wallet", "Wallet"), ("insurance", "Insurance")], max_length=24)),
                ("reference", models.CharField(blank=True, default="", max_length=140)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("failed", "Failed"), ("refunded", "Refunded"), ("void", "Void")], default="pending", max_length=20)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="payments.invoice")),
                ("received_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="received_payments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="paymenttransaction", index=models.Index(fields=["invoice", "status"], name="pay_tx_invoice_stat_idx")),
        migrations.CreateModel(
            name="Receipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=30, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_receipts", to=settings.AUTH_USER_MODEL)),
                ("payment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="receipt", to="payments.paymenttransaction")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CashierShift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("opening_float", models.PositiveBigIntegerField(default=0)),
                ("expected_cash", models.PositiveBigIntegerField(default=0)),
                ("closing_cash", models.PositiveBigIntegerField(blank=True, null=True)),
                ("variance", models.BigIntegerField(default=0)),
                ("status", models.CharField(choices=[("open", "Open"), ("closed", "Closed")], default="open", max_length=20)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("cashier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cashier_shifts", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cashier_shifts", to="registry.organization")),
            ],
            options={"ordering": ["-opened_at"]},
        ),
        migrations.AddIndex(model_name="cashiershift", index=models.Index(fields=["organization", "status", "opened_at"], name="pay_shift_org_stat_idx")),
    ]
