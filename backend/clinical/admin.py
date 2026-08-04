from django.contrib import admin

from .models import (
    Allergy,
    CarePlan,
    ClinicalEncounter,
    Condition,
    EncounterRevision,
    MedicationStatement,
    Observation,
    Referral,
    ReferralStatusHistory,
)


class ReferralStatusInline(admin.TabularInline):
    model = ReferralStatusHistory
    extra = 0
    readonly_fields = ("actor", "from_status", "to_status", "reason", "metadata", "created_at")


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "referring_provider", "target_provider", "target_specialty", "priority", "status", "created_at")
    list_filter = ("priority", "status", "target_specialty")
    search_fields = ("patient__email", "patient__first_name", "patient__last_name", "reason", "target_specialty")
    inlines = (ReferralStatusInline,)


for model in (Allergy, CarePlan, ClinicalEncounter, Condition, EncounterRevision, MedicationStatement, Observation):
    admin.site.register(model)
