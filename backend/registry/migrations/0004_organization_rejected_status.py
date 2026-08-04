from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0003_organization_documents_and_services"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organization",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending verification"),
                    ("verified", "Verified"),
                    ("rejected", "Rejected"),
                    ("suspended", "Suspended"),
                    ("inactive", "Inactive"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
