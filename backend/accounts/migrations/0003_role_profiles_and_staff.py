import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


PROFILE_STATUS = [
    ('pending', 'Pending verification'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
    ('suspended', 'Suspended'),
    ('expired', 'Expired'),
    ('revoked', 'Revoked'),
]


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_doctorprofile_patientprofile_providerprofile')]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('patient', 'Patient'), ('doctor', 'Doctor'),
                    ('nurse', 'Nurse / Midwife'), ('receptionist', 'Receptionist'),
                    ('cashier', 'Cashier / Billing officer'), ('pharmacist', 'Pharmacist'),
                    ('lab_technician', 'Laboratory professional'),
                    ('facility_manager', 'Facility manager'),
                    ('records_officer', 'Medical records officer'),
                    ('insurance_officer', 'Insurance officer'),
                    ('storekeeper', 'Storekeeper / Procurement'),
                    ('pharmacy', 'Pharmacy organization'), ('lab', 'Laboratory organization'),
                    ('hospital', 'Hospital / Clinic organization'),
                    ('insurance', 'Insurance organization'), ('admin', 'Platform administrator'),
                ],
                default='patient', max_length=24,
            ),
        ),
        migrations.AddField(model_name='patientprofile', name='location', field=models.CharField(blank=True, default='', max_length=180)),
        migrations.AlterField(
            model_name='patientprofile', name='gender',
            field=models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other'), ('prefer_not_to_say', 'Prefer not to say')], default='', max_length=20),
        ),
        migrations.AddField(
            model_name='doctorprofile', name='year_of_completion',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1950), django.core.validators.MaxValueValidator(2100)]),
        ),
        migrations.AddField(model_name='doctorprofile', name='university', field=models.CharField(blank=True, default='', max_length=220)),
        migrations.AddField(
            model_name='doctorprofile', name='cadre',
            field=models.CharField(blank=True, choices=[('medical_officer', 'Medical Officer'), ('specialist', 'Specialist Doctor'), ('consultant', 'Consultant'), ('clinical_officer', 'Clinical Officer'), ('dentist', 'Dentist'), ('other', 'Other')], default='', max_length=40),
        ),
        migrations.AddField(model_name='doctorprofile', name='license_number', field=models.CharField(blank=True, default='', max_length=140)),
        migrations.AddField(model_name='doctorprofile', name='license_issuer', field=models.CharField(blank=True, default='', max_length=180)),
        migrations.AddField(model_name='doctorprofile', name='license_expires_on', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='doctorprofile', name='verification_notes', field=models.TextField(blank=True, default='')),
        migrations.AlterField(model_name='doctorprofile', name='status', field=models.CharField(choices=PROFILE_STATUS, default='pending', max_length=20)),
        migrations.AddIndex(model_name='doctorprofile', index=models.Index(fields=['license_number', 'status'], name='accounts_do_license_91c6a1_idx')),
        migrations.AddField(model_name='providerprofile', name='license_document', field=models.FileField(blank=True, null=True, upload_to='organizations/licenses/')),
        migrations.AddField(model_name='providerprofile', name='district', field=models.CharField(blank=True, default='', max_length=120)),
        migrations.AddField(model_name='providerprofile', name='services_description', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='providerprofile', name='verification_notes', field=models.TextField(blank=True, default='')),
        migrations.AlterField(model_name='providerprofile', name='status', field=models.CharField(choices=PROFILE_STATUS, default='pending', max_length=20)),
        migrations.CreateModel(
            name='StaffProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('employee_number', models.CharField(blank=True, default='', max_length=80)),
                ('cadre', models.CharField(blank=True, default='', max_length=120)),
                ('university', models.CharField(blank=True, default='', max_length=220)),
                ('year_of_completion', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('qualification', models.CharField(blank=True, default='', max_length=220)),
                ('registration_number', models.CharField(blank=True, default='', max_length=140)),
                ('license_issuer', models.CharField(blank=True, default='', max_length=180)),
                ('license_expires_on', models.DateField(blank=True, null=True)),
                ('license_document', models.FileField(blank=True, null=True, upload_to='staff/licenses/')),
                ('bio', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=PROFILE_STATUS, default='pending', max_length=20)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='staff_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(model_name='staffprofile', index=models.Index(fields=['registration_number', 'status'], name='accounts_st_registr_0d1cc4_idx')),
    ]
