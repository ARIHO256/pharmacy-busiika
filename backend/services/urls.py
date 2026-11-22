from django.urls import path

from . import pharmacy_prescription_views as rx, views
from .pharmacy_sales import PharmacyCounterSaleView, PharmacySaleReceiptView, PharmacyShiftCloseView, PharmacyShiftView

from .pharmacy_finance import PharmacyCreditPaymentView, PharmacyCreditView, PharmacyRefundView
from .pharmacy_support import BuyerAddressView, PharmacyIssueView, PrescriberIssueView
from .pharmacy_workbench import PharmacyAuditView, PharmacyStockAlertsView, PharmacyStockSetupView
from .pharmacy_reports import PharmacyReportsView
from .pharmacy_permissions import PharmacyRolePolicyView, bound_view
from .taxonomy_views import TaxonomyManagementView, TaxonomyNodeManagementView

urlpatterns = [
    # Public provider directories
    path("pharmacies/", views.PharmacyListView.as_view()),
    path("labs/", views.LabListView.as_view()),
    path("hospitals/", views.HospitalListView.as_view()),
    path("insurers/", views.InsurerListView.as_view()),

    # Pharmacy
    path("pharmacy/refunds/", PharmacyRefundView.as_view()),
    path("pharmacy/credit/", PharmacyCreditView.as_view()),
    path("pharmacy/credit/<int:pk>/payments/", PharmacyCreditPaymentView.as_view()),
    path("pharmacy/buyer-address/", BuyerAddressView.as_view()),
    path("pharmacy/prescriber-issues/", PrescriberIssueView.as_view()),
    path("pharmacy/prescriber-issues/<int:pk>/", PrescriberIssueView.as_view()),
    path("pharmacy/issues/<str:kind>/<int:pk>/", PharmacyIssueView.as_view()),
    path("pharmacy/issues/<str:kind>/<int:pk>/<int:issue>/", PharmacyIssueView.as_view()),
    path("pharmacy/stock-setup/", PharmacyStockSetupView.as_view()),
    path("pharmacy/stock-alerts/", PharmacyStockAlertsView.as_view()),
    path("pharmacy/audit/", PharmacyAuditView.as_view()),
    path("pharmacy/reports/", PharmacyReportsView.as_view()),
    path("pharmacy/role-permissions/", PharmacyRolePolicyView.as_view()),
    path("medicine-taxonomy/manage/", TaxonomyManagementView.as_view()),
    path("medicine-taxonomy/manage/<slug:node_id>/", TaxonomyNodeManagementView.as_view()),
    path("medicine-taxonomy/", bound_view(views.MedicineTaxonomyView, "inventory")),
    path("medicines/", bound_view(views.MedicineListCreateView, "inventory", write="catalogue_edit")),
    path("medicines/<int:pk>/", bound_view(views.MedicineDetailView, "inventory", write="catalogue_edit")),
    path("pharmacy/wholesale/cart/", views.CartListCreateView.as_view(wholesale_only=True)),
    path("pharmacy/wholesale/checkout/", views.CheckoutView.as_view(wholesale_only=True)),
    path("cart/", views.CartListCreateView.as_view()),
    path("cart/<int:pk>/", views.CartDetailView.as_view()),
    path("orders/checkout/", views.CheckoutView.as_view()),
    path("orders/", bound_view(views.OrderListView, "orders")),
    path("pharmacy/counter-sales/", bound_view(PharmacyCounterSaleView, "counter", write="sell")),
    path("pharmacy/shifts/", bound_view(PharmacyShiftView, "shifts", write="shift_manage")),
    path("pharmacy/shifts/<int:pk>/close/", bound_view(PharmacyShiftCloseView, "shifts", write="shift_manage")),
    path("orders/<int:pk>/receipt/", bound_view(PharmacySaleReceiptView, "orders", write="payment", read="receipt_print")),
    path("orders/<int:pk>/update/", bound_view(views.OrderUpdateView, "orders", write="fulfil")),
    path("pharmacy-orders/", bound_view(views.PharmacyOrderListView, "rx-orders")),
    path("pharmacy-orders/<int:pk>/update/", bound_view(views.PharmacyOrderUpdateView, "rx-orders", write="rx_manage")),
    path("pharmacy-orders/<int:pk>/review/", bound_view(rx.PharmacyPrescriptionReviewView, "rx-orders", write="rx_manage")),
    path("pharmacy-orders/<int:pk>/substitutions/", bound_view(rx.PharmacySubstitutionRequestView, "rx-orders", write="rx_manage")),
    path("pharmacy-substitutions/", rx.PrescriberSubstitutionView.as_view()),
    path("pharmacy-substitutions/<int:pk>/", rx.PrescriberSubstitutionView.as_view()),
    path("suppliers/", bound_view(views.SupplierListCreateView, "suppliers", write="supplier_edit")),
    path("suppliers/<int:pk>/", bound_view(views.SupplierDetailView, "suppliers", write="supplier_edit")),

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
