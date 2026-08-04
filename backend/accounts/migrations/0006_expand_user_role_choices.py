from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_security_tokens_and_account_controls")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("patient", "Patient"), ("doctor", "Doctor"), ("nurse", "Nurse"),
                    ("midwife", "Midwife"), ("clinical_officer", "Clinical officer"),
                    ("dentist", "Dentist"), ("radiologist", "Radiologist"),
                    ("radiographer", "Radiographer"), ("physiotherapist", "Physiotherapist"),
                    ("nutritionist", "Nutritionist"), ("psychologist", "Psychologist"),
                    ("anaesthetist", "Anaesthetist"), ("theatre_nurse", "Theatre nurse"),
                    ("medical_director", "Medical director"), ("receptionist", "Receptionist"),
                    ("records_officer", "Records officer"), ("cashier", "Cashier"),
                    ("accountant", "Accountant"), ("finance_manager", "Finance manager"),
                    ("pharmacist", "Pharmacist"), ("lab_technician", "Laboratory professional"),
                    ("facility_manager", "Facility manager"), ("procurement_officer", "Procurement officer"),
                    ("quality_officer", "Quality officer"), ("compliance_officer", "Compliance officer"),
                    ("hr_officer", "Human resources officer"), ("it_support", "IT support"),
                    ("insurance_officer", "Insurance officer"), ("claims_reviewer", "Claims reviewer"),
                    ("storekeeper", "Storekeeper"), ("ambulance_dispatcher", "Ambulance dispatcher"),
                    ("paramedic", "Paramedic"), ("pharmacy", "Pharmacy"),
                    ("lab", "Laboratory"), ("hospital", "Hospital / Clinic"),
                    ("insurance", "Insurance Organization"), ("admin", "Admin"),
                ],
                default="patient",
                max_length=32,
            ),
        ),
    ]
