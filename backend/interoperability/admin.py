from django.contrib import admin

from .models import ConceptMapping, OutboxEvent, TerminologyConcept


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "aggregate_type", "aggregate_id", "status", "attempts", "occurred_at")
    list_filter = ("status", "event_type")
    readonly_fields = [field.name for field in OutboxEvent._meta.fields]

    def has_add_permission(self, request):
        return False


admin.site.register(TerminologyConcept)
admin.site.register(ConceptMapping)
