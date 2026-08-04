from django.urls import path

from .admin_views import (
    AdminGlobalSearchView, AdminOrganizationOwnershipView, AdminRoleContextDetailView,
    AdminRoleContextListCreateView, AdminSystemHealthView, AdminUserActionView, AdminUserDetailView,
)
from .views import (
    GeneratedDocumentDownloadView,
    GeneratedDocumentListCreateView,
    PageCaseListCreateView,
    PageDefinitionView,
    PageOperationalDataView,
    OperationalActionListView, ProductionReadinessView, PublicDocumentVerificationView,
    ReleaseAcceptanceDetailView, ReleaseAcceptanceListCreateView,
    WorkflowCaseActionView,
    WorkflowCaseDetailView,
    WorkflowCommentListCreateView,
    WorkflowDashboardView,
)

urlpatterns = [
    path("admin/search/", AdminGlobalSearchView.as_view(), name="journey-admin-search"),
    path("admin/users/<int:pk>/", AdminUserDetailView.as_view(), name="journey-admin-user-detail"),
    path("admin/users/<int:pk>/actions/", AdminUserActionView.as_view(), name="journey-admin-user-action"),
    path("admin/users/<int:user_id>/contexts/", AdminRoleContextListCreateView.as_view(), name="journey-admin-role-contexts"),
    path("admin/contexts/<int:pk>/", AdminRoleContextDetailView.as_view(), name="journey-admin-role-context-detail"),
    path("admin/organizations/<int:pk>/ownership/", AdminOrganizationOwnershipView.as_view(), name="journey-admin-organization-owner"),
    path("admin/system-health/", AdminSystemHealthView.as_view(), name="journey-admin-system-health"),
    path("dashboard/", WorkflowDashboardView.as_view(), name="journey-dashboard"),
    path("operational-actions/", OperationalActionListView.as_view(), name="journey-operational-actions"),
    path("release-acceptances/", ReleaseAcceptanceListCreateView.as_view(), name="journey-release-acceptances"),
    path("release-acceptances/<int:pk>/", ReleaseAcceptanceDetailView.as_view(), name="journey-release-acceptance-detail"),
    path("production-readiness/", ProductionReadinessView.as_view(), name="journey-production-readiness"),
    path("pages/<slug:slug>/definition/", PageDefinitionView.as_view(), name="journey-page-definition"),
    path("pages/<slug:slug>/data/", PageOperationalDataView.as_view(), name="journey-page-data"),
    path("pages/<slug:slug>/cases/", PageCaseListCreateView.as_view(), name="journey-page-cases"),
    path("cases/<uuid:public_id>/", WorkflowCaseDetailView.as_view(), name="journey-case-detail"),
    path("cases/<uuid:public_id>/action/", WorkflowCaseActionView.as_view(), name="journey-case-action"),
    path("cases/<uuid:public_id>/actions/", WorkflowCaseActionView.as_view(), name="journey-case-actions"),
    path("cases/<uuid:public_id>/comments/", WorkflowCommentListCreateView.as_view(), name="journey-case-comments"),
    path("documents/", GeneratedDocumentListCreateView.as_view(), name="journey-documents"),
    path("documents/<uuid:public_id>/download/", GeneratedDocumentDownloadView.as_view(), name="journey-document-download"),
    path("documents/verify/<str:code>/", PublicDocumentVerificationView.as_view(), name="journey-document-verify"),
]
