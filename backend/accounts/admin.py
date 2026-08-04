from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    DoctorProfile,
    OneTimeToken,
    PatientProfile,
    PatientRelationship,
    ProviderProfile,
    SecurityEvent,
    StaffProfile,
    User,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "display_name", "role", "is_verified", "is_active", "date_joined")
    list_filter = ("role", "is_verified", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identity", {"fields": ("first_name", "last_name", "phone", "role")}),
        ("Verification", {"fields": ("is_verified", "email_verified_at", "phone_verified_at", "mfa_enabled", "locked_until")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined", "last_password_change_at")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role", "is_staff", "is_active")}),)


@admin.register(PatientRelationship)
class PatientRelationshipAdmin(admin.ModelAdmin):
    list_display = ("caregiver", "patient", "relationship", "status", "can_book", "can_view_records", "expires_at")
    list_filter = ("relationship", "status", "can_book", "can_view_records", "can_manage_billing")
    search_fields = ("caregiver__email", "patient__email", "patient__first_name", "patient__last_name")
    readonly_fields = ("created_at", "updated_at")


for model in (PatientProfile, DoctorProfile, ProviderProfile, StaffProfile, OneTimeToken, SecurityEvent):
    admin.site.register(model)
