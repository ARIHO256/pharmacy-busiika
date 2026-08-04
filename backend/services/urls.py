from django.urls import path

from . import views

urlpatterns = [
    # Public provider directories
    path("pharmacies/", views.PharmacyListView.as_view()),
    path("labs/", views.LabListView.as_view()),
    path("hospitals/", views.HospitalListView.as_view()),
    path("insurers/", views.InsurerListView.as_view()),

    # Pharmacy
    path("medicines/", views.MedicineListCreateView.as_view()),
    path("medicines/<int:pk>/", views.MedicineDetailView.as_view()),
    path("cart/", views.CartListCreateView.as_view()),
    path("cart/<int:pk>/", views.CartDetailView.as_view()),
    path("orders/checkout/", views.CheckoutView.as_view()),
    path("orders/", views.OrderListView.as_view()),
    path("orders/<int:pk>/update/", views.OrderUpdateView.as_view()),
    path("pharmacy-orders/", views.PharmacyOrderListView.as_view()),
    path("pharmacy-orders/<int:pk>/update/", views.PharmacyOrderUpdateView.as_view()),
    path("pharmacy-orders/<int:pk>/dispensing/", views.DispensingRecordListCreateView.as_view()),
    path("suppliers/", views.SupplierListCreateView.as_view()),
    path("suppliers/<int:pk>/", views.SupplierDetailView.as_view()),

    # Lab
    path("lab-panels/", views.LabTestPanelListCreateView.as_view()),
    path("lab-panels/<int:pk>/", views.LabTestPanelDetailView.as_view()),
    path("lab-panels/<int:pk>/order/", views.LabTestPanelOrderView.as_view()),
    path("lab-tests/", views.LabTestListCreateView.as_view()),
    path("lab-tests/<int:pk>/", views.LabTestDetailView.as_view()),
    path("lab-orders/", views.LabOrderListCreateView.as_view()),
    path("lab-orders/manage/", views.LabOrderManageView.as_view()),
    path("lab-orders/<int:pk>/update/", views.LabOrderUpdateView.as_view()),
    path("lab-orders/<int:pk>/results/", views.LabResultListCreateView.as_view()),
    path("lab-orders/<int:pk>/specimen-events/", views.SpecimenEventListCreateView.as_view()),
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
    path("policies/<int:policy_id>/benefits/", views.BenefitRuleListCreateView.as_view()),
    path("policy-benefits/<int:pk>/", views.BenefitRuleDetailView.as_view()),
    path("coverage/verify/", views.CoverageVerifyView.as_view()),
    path("coverage/eligibility-history/", views.EligibilityHistoryView.as_view()),
    path("coverage/", views.CoverageListCreateView.as_view()),
    path("preauthorizations/", views.PreauthorizationListCreateView.as_view()),
    path("preauthorizations/<int:pk>/decide/", views.PreauthorizationDecisionView.as_view()),
    path("claims/", views.ClaimListCreateView.as_view()),
    path("claims/manage/", views.ClaimManageView.as_view()),
    path("claims/<int:pk>/decide/", views.ClaimDecideView.as_view()),
    path("remittances/", views.RemittanceListView.as_view()),
]
