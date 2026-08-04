from django.contrib import admin

from .models import (
    Department,
    MedicationAdministration,
    NursingNote,
    PatientVisit,
    StaffInvitation,
    StaffMembership,
    TriageRecord,
)

admin.site.register(Department)
admin.site.register(StaffMembership)
admin.site.register(StaffInvitation)
admin.site.register(PatientVisit)
admin.site.register(TriageRecord)
admin.site.register(NursingNote)
admin.site.register(MedicationAdministration)
