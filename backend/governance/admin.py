from django.contrib import admin

from .models import AuditEvent, BreakGlassAccess, Consent


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ("patient", "consent_type", "status", "granted_to", "granted_at")
    list_filter = ("consent_type", "status")
    search_fields = ("patient__email", "granted_to__email")


@admin.register(BreakGlassAccess)
class BreakGlassAccessAdmin(admin.ModelAdmin):
    list_display = ("requester", "patient", "status", "started_at", "expires_at")
    list_filter = ("status",)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "patient", "decision", "created_at")
    list_filter = ("decision", "emergency_access")
    search_fields = ("action", "actor__email", "patient__email", "resource_id")
    readonly_fields = [field.name for field in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
