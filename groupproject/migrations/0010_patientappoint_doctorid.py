# Generated by Django 3.2.6 on 2023-04-22 18:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('groupproject', '0009_auto_20230422_1758'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientappoint',
            name='doctorid',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]