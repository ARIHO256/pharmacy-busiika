from django.contrib import admin
from . import models


@admin.register(models.RoleContext)
class RoleContextAdmin(admin.ModelAdmin):
    list_display = ("user", "role_code", "organization", "location", "department", "active", "is_primary")
    list_filter = ("role_code", "active", "is_primary", "organization")
    search_fields = ("user__email", "user__first_name", "user__last_name", "title", "organization__legal_name")


@admin.register(models.EnterpriseRecord)
class EnterpriseRecordAdmin(admin.ModelAdmin):
    list_display = ("reference", "record_type", "organization", "patient", "status", "priority", "occurred_at")
    list_filter = ("domain", "record_type", "status", "priority", "organization")
    search_fields = ("reference", "title", "summary", "patient__email")
    readonly_fields = ("public_id", "reference", "created_at", "updated_at")


for model in (
    models.ActiveRoleContext, models.RoleDelegation, models.WorkflowTransition,
    models.ResourceAttachment, models.ClinicalCode, models.TariffSchedule,
    models.PayerContract, models.MedicationKnowledge, models.MedicationInteraction,
    models.PACSNode, models.ImagingStudy, models.AmbulanceVehicle,
    models.AmbulanceTelemetry, models.PresenceState, models.MessageReceipt,
    models.TelemedicineSession, models.TelemedicineParticipant,
    models.NotificationProvider, models.CommunicationConsent, models.EscalationPolicy,
    models.EscalationStep, models.EventSchema, models.IntegrationEndpoint,
    models.EventDelivery, models.DeadLetterEvent, models.ReplayRequest,
    models.ContentEntry, models.FeatureConfiguration, models.MasterPatientIndex,
    models.DuplicatePatientCandidate, models.PatientMerge, models.RecordsRequest,
    models.FHIRResource, models.PartnerApplication, models.PartnerAccessToken,
    models.FHIRSubscription, models.RegulatorConnector, models.VerificationAutomation,
    models.SecurityOperation, models.SavedReport, models.ReportRun, models.ReportSchedule,
):
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
