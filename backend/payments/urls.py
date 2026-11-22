from django.urls import path

from .views import (
    BillingSummaryView,
    CashierInvoiceListCreateView,
    CashierRecordPaymentView,
    CashierShiftCloseView,
    CashierShiftListCreateView,
    EarningsView,
    InitiatePaymentView,
    InvoiceListView,
    MockWebhookView,
    ReceiptDetailView,
    ReceiptView,
    WithdrawView,
)

urlpatterns = [
    path("payments/initiate/", InitiatePaymentView.as_view(), name="payment-initiate"),
    path("payments/webhook/mock/<str:invoice_number>/", MockWebhookView.as_view(), name="payment-webhook-mock"),
    path("payments/invoices/", InvoiceListView.as_view(), name="invoices"),
    path("payments/invoices/<int:pk>/receipt/", ReceiptView.as_view(), name="invoice-receipt"),
    path("payments/receipts/<int:pk>/", ReceiptDetailView.as_view(), name="receipt-detail"),
    path("billing/invoices/", CashierInvoiceListCreateView.as_view(), name="cashier-invoices"),
    path("billing/invoices/<int:pk>/payments/", CashierRecordPaymentView.as_view(), name="cashier-record-payment"),
    path("billing/shifts/", CashierShiftListCreateView.as_view(), name="cashier-shifts"),
    path("billing/shifts/<int:pk>/close/", CashierShiftCloseView.as_view(), name="cashier-shift-close"),
    path("billing/summary/", BillingSummaryView.as_view(), name="billing-summary"),
    path("payments/earnings/", EarningsView.as_view(), name="earnings"),
    path("payments/withdraw/", WithdrawView.as_view(), name="withdraw"),
]
