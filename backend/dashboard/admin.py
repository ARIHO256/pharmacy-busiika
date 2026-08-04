from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "action", "created_at")
    readonly_fields = ("user", "action", "meta", "created_at")
