from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("workforce", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="PermissionDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=120, unique=True)),
                ("name", models.CharField(max_length=180)),
                ("module", models.CharField(max_length=80)),
                ("description", models.TextField(blank=True, default="")),
                ("sensitive", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["module", "name"]},
        ),
        migrations.CreateModel(
            name="FacilityRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.SlugField(max_length=80)),
                ("description", models.TextField(blank=True, default="")),
                ("active", models.BooleanField(default=True)),
                ("is_system", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_facility_roles", to="accounts.user")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="custom_roles", to="registry.organization")),
            ],
            options={"ordering": ["organization", "name"]},
        ),
        migrations.CreateModel(
            name="FacilityRolePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("granted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="granted_facility_permissions", to="accounts.user")),
                ("permission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_links", to="workforce.permissiondefinition")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="permission_links", to="workforce.facilityrole")),
            ],
        ),
        migrations.AddField(
            model_name="facilityrole",
            name="permissions",
            field=models.ManyToManyField(related_name="facility_roles", through="workforce.FacilityRolePermission", to="workforce.permissiondefinition"),
        ),
        migrations.CreateModel(
            name="MembershipRoleAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valid_from", models.DateTimeField(default=django.utils.timezone.now)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_custom_roles", to="accounts.user")),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="custom_role_assignments", to="workforce.staffmembership")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="membership_assignments", to="workforce.facilityrole")),
            ],
        ),
        migrations.AddConstraint(model_name="facilityrole", constraint=models.UniqueConstraint(fields=("organization", "code"), name="unique_facility_role_code")),
        migrations.AddConstraint(model_name="facilityrolepermission", constraint=models.UniqueConstraint(fields=("role", "permission"), name="unique_permission_per_facility_role")),
        migrations.AddConstraint(model_name="membershiproleassignment", constraint=models.UniqueConstraint(fields=("membership", "role"), name="unique_custom_role_assignment")),
    ]
