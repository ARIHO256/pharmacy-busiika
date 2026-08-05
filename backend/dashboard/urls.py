from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.AdminOverviewView.as_view()),
    path("users/", views.AdminUsersView.as_view()),
    path("users/<int:pk>/set-status/", views.AdminUserSetStatusView.as_view()),
    path("users/<int:pk>/set-role/", views.AdminUserSetRoleView.as_view()),
    path("appointments/", views.AdminAppointmentsView.as_view()),
    path("analytics/appointments/", views.AdminAppointmentAnalyticsView.as_view()),
    path("finance/", views.AdminFinanceView.as_view()),
    path("reviews/", views.AdminReviewsView.as_view()),
    path("reviews/<int:pk>/action/", views.AdminReviewActionView.as_view()),
    path("notifications/broadcast/", views.AdminBroadcastView.as_view()),
    path("audit/", views.AdminAuditView.as_view()),
]
