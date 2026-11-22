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
)

admin.site.register(ClinicalEncounter)
admin.site.register(EncounterRevision)
admin.site.register(Allergy)
admin.site.register(Condition)
admin.site.register(MedicationStatement)
admin.site.register(Observation)
admin.site.register(Referral)
admin.site.register(CarePlan)
