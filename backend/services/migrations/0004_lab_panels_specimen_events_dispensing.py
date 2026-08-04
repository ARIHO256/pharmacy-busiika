import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0003_laboratory_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LabTestPanel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("code", models.CharField(max_length=80)),
                ("description", models.TextField(blank=True, default="")),
                ("price", models.PositiveIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lab", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lab_test_panels", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="DispensingRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("reviewed", "Prescription reviewed"), ("clarification", "Clarification required"), ("partial", "Partially dispensed"), ("dispensed", "Dispensed"), ("held", "Held"), ("cancelled", "Cancelled")], default="reviewed", max_length=24)),
                ("clarification_note", models.TextField(blank=True, default="")),
                ("substitution_authorised_by", models.CharField(blank=True, default="", max_length=200)),
                ("counselling_notes", models.TextField(blank=True, default="")),
                ("dispensed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pharmacist", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dispensing_records", to=settings.AUTH_USER_MODEL)),
                ("pharmacy_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dispensing_records", to="services.pharmacyorder")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SpecimenEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("labelled", "Label generated"), ("collected", "Collected"), ("received", "Received"), ("aliquoted", "Aliquoted"), ("transferred", "Transferred"), ("processing", "Processing"), ("stored", "Stored"), ("rejected", "Rejected"), ("disposed", "Disposed")], max_length=24)),
                ("barcode", models.CharField(blank=True, default="", max_length=100)),
                ("location", models.CharField(blank=True, default="", max_length=180)),
                ("notes", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="specimen_events", to="services.laborder")),
                ("performed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="laboratory_specimen_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["occurred_at", "id"]},
        ),
        migrations.CreateModel(
            name="LabTestPanelItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveSmallIntegerField(default=1)),
                ("required", models.BooleanField(default=True)),
                ("panel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="services.labtestpanel")),
                ("test", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="panel_items", to="services.labtest")),
            ],
            options={"ordering": ["sequence", "id"]},
        ),
        migrations.CreateModel(
            name="DispensingItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prescription_item_id", models.PositiveIntegerField(blank=True, null=True)),
                ("medicine_name", models.CharField(max_length=220)),
                ("prescribed_quantity", models.PositiveIntegerField(default=0)),
                ("dispensed_quantity", models.PositiveIntegerField(default=0)),
                ("batch_number", models.CharField(blank=True, default="", max_length=100)),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("substituted_product", models.CharField(blank=True, default="", max_length=220)),
                ("label_instructions", models.TextField(blank=True, default="")),
                ("record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="services.dispensingrecord")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddConstraint(
            model_name="labtestpanel",
            constraint=models.UniqueConstraint(fields=("lab", "code"), name="unique_lab_panel_code"),
        ),
        migrations.AddIndex(
            model_name="labtestpanel",
            index=models.Index(fields=["lab", "active", "name"], name="services_panel_lab_idx"),
        ),
        migrations.AddConstraint(
            model_name="labtestpanelitem",
            constraint=models.UniqueConstraint(fields=("panel", "test"), name="unique_test_in_lab_panel"),
        ),
        migrations.AddIndex(
            model_name="specimenevent",
            index=models.Index(fields=["order", "occurred_at"], name="services_spec_order_idx"),
        ),
        migrations.AddIndex(
            model_name="specimenevent",
            index=models.Index(fields=["barcode"], name="services_spec_barcode_idx"),
        ),
        migrations.AddIndex(
            model_name="dispensingrecord",
            index=models.Index(fields=["pharmacy_order", "status"], name="services_disp_order_idx"),
        ),
        migrations.AddIndex(
            model_name="dispensingrecord",
            index=models.Index(fields=["pharmacist", "created_at"], name="services_disp_staff_idx"),
        ),
        migrations.AddConstraint(
            model_name="dispensingitem",
            constraint=models.UniqueConstraint(fields=("record", "prescription_item_id", "medicine_name"), name="unique_dispensing_record_item"),
        ),
    ]
