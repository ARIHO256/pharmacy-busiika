from django.urls import path

from . import pharmacy_prescription_views as rx, views
from .pharmacy_sales import PharmacyCounterSaleView, PharmacySaleReceiptView, PharmacyShiftCloseView, PharmacyShiftView

from .taxonomy_views import TaxonomyManagementView, TaxonomyNodeManagementView

urlpatterns = [
    # Public provider directories
    path("pharmacies/", views.PharmacyListView.as_view()),
    path("labs/", views.LabListView.as_view()),
    path("hospitals/", views.HospitalListView.as_view()),
    path("insurers/", views.InsurerListView.as_view()),

    # Pharmacy
    path("medicine-taxonomy/manage/", TaxonomyManagementView.as_view()),
    path("medicine-taxonomy/manage/<slug:node_id>/", TaxonomyNodeManagementView.as_view()),
    path("medicine-taxonomy/", views.MedicineTaxonomyView.as_view()),
    path("medicines/", views.MedicineListCreateView.as_view()),
    path("medicines/<int:pk>/", views.MedicineDetailView.as_view()),
    path("cart/", views.CartListCreateView.as_view()),
    path("cart/<int:pk>/", views.CartDetailView.as_view()),
    path("orders/checkout/", views.CheckoutView.as_view()),
    path("orders/", views.OrderListView.as_view()),
    path("pharmacy/counter-sales/", PharmacyCounterSaleView.as_view()),
    path("pharmacy/shifts/", PharmacyShiftView.as_view()),
    path("pharmacy/shifts/<int:pk>/close/", PharmacyShiftCloseView.as_view()),
    path("orders/<int:pk>/receipt/", PharmacySaleReceiptView.as_view()),
    path("orders/<int:pk>/update/", views.OrderUpdateView.as_view()),
    path("pharmacy-orders/", views.PharmacyOrderListView.as_view()),
    path("pharmacy-orders/<int:pk>/update/", views.PharmacyOrderUpdateView.as_view()),
    path("pharmacy-orders/<int:pk>/review/", rx.PharmacyPrescriptionReviewView.as_view()),
    path("pharmacy-orders/<int:pk>/substitutions/", rx.PharmacySubstitutionRequestView.as_view()),
    path("pharmacy-substitutions/", rx.PrescriberSubstitutionView.as_view()),
    path("pharmacy-substitutions/<int:pk>/", rx.PrescriberSubstitutionView.as_view()),
    path("suppliers/", views.SupplierListCreateView.as_view()),
    path("suppliers/<int:pk>/", views.SupplierDetailView.as_view()),

    # Lab
    path("lab-tests/", views.LabTestListCreateView.as_view()),
    path("lab-tests/<int:pk>/", views.LabTestDetailView.as_view()),
    path("lab-orders/", views.LabOrderListCreateView.as_view()),
    path("lab-orders/manage/", views.LabOrderManageView.as_view()),
    path("lab-orders/<int:pk>/update/", views.LabOrderUpdateView.as_view()),
    path("lab-orders/<int:pk>/results/", views.LabResultListCreateView.as_view()),
    path("lab-results/<int:pk>/acknowledge/", views.CriticalResultAcknowledgeView.as_view()),

    # Hospital
    path("hospital-services/", views.HospitalServiceListCreateView.as_view()),
    path("hospital-services/<int:pk>/", views.HospitalServiceDetailView.as_view()),
    path("hospital-bookings/", views.HospitalBookingListCreateView.as_view()),
    path("hospital-bookings/manage/", views.HospitalBookingManageView.as_view()),
    path("hospital-bookings/<int:pk>/update/", views.HospitalBookingUpdateView.as_view()),
    path("beds/", views.BedListCreateView.as_view()),
    path("beds/<int:pk>/", views.BedDetailView.as_view()),
    path("beds/<int:pk>/toggle/", views.BedToggleView.as_view()),

    # Insurance
    path("policies/", views.PolicyListCreateView.as_view()),
    path("policies/<int:pk>/", views.PolicyDetailView.as_view()),
    path("coverage/verify/", views.CoverageVerifyView.as_view()),
    path("coverage/", views.CoverageListCreateView.as_view()),
    path("claims/", views.ClaimListCreateView.as_view()),
    path("claims/manage/", views.ClaimManageView.as_view()),
    path("claims/<int:pk>/decide/", views.ClaimDecideView.as_view()),
]
