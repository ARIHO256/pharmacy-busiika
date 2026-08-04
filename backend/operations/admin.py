from django.contrib import admin
from .models import *

for model in [
    Ward, FacilityBed, Admission, BedAllocation, AdmissionTransfer, WardTask,
    ClinicalRound, DischargeSummary, ImagingOrder, ImagingReport, InventoryItem,
    InventoryBatch, StockMovement, PurchaseOrder, PurchaseOrderItem, SubscriptionPlan,
    AccountSubscription, SupportTicket, Announcement, EmergencyCase, AmbulanceDispatch,
    SurgicalCase, SurgicalChecklist, MaternityEpisode, StaffShift, LeaveRequest,
    QualityIncident, PrivacyRequest,
]:
    admin.site.register(model)
