from django.contrib import admin

from .models import (
    Bed,
    CartItem,
    CriticalResultAcknowledgement,
    DispensingItem,
    DispensingRecord,
    HospitalBooking,
    HospitalService,
    InsuranceClaim,
    InsurancePolicy,
    LabOrder,
    LabResult,
    LabTest,
    LabTestPanel,
    LabTestPanelItem,
    Medicine,
    Order,
    OrderItem,
    PatientCoverage,
    PharmacyOrder,
    SpecimenEvent,
    Supplier,
    SupplierProduct,
)


class LabPanelItemInline(admin.TabularInline):
    model = LabTestPanelItem
    extra = 0


@admin.register(LabTestPanel)
class LabTestPanelAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "lab", "price", "active")
    list_filter = ("active", "lab")
    search_fields = ("name", "code", "lab__email")
    inlines = [LabPanelItemInline]


class DispensingItemInline(admin.TabularInline):
    model = DispensingItem
    extra = 0


@admin.register(DispensingRecord)
class DispensingRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "pharmacy_order", "pharmacist", "status", "dispensed_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("pharmacist__email", "pharmacy_order__patient__email")
    inlines = [DispensingItemInline]


@admin.register(SpecimenEvent)
class SpecimenEventAdmin(admin.ModelAdmin):
    list_display = ("order", "event_type", "barcode", "location", "performed_by", "occurred_at")
    list_filter = ("event_type", "occurred_at")
    search_fields = ("barcode", "order__patient__email", "notes")


for model in [
    Medicine, CartItem, Order, OrderItem, PharmacyOrder, Supplier, SupplierProduct,
    LabTest, LabOrder, LabResult, CriticalResultAcknowledgement,
    HospitalService, HospitalBooking, Bed,
    InsurancePolicy, PatientCoverage, InsuranceClaim,
]:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
