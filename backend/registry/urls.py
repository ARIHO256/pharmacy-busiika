from django.urls import path

from .views import (
    CareRelationshipListView,
    MyOrganizationListView,
    OrganizationDetailView,
    OrganizationListCreateView,
    OrganizationLocationListCreateView,
    OrganizationLicenseDocumentView,
    OrganizationStatusView,
    PractitionerCredentialListCreateView,
    PractitionerCredentialDocumentView,
    PractitionerCredentialVerifyView,
    PractitionerRoleListCreateView,
)

urlpatterns = [
    path("organizations/", OrganizationListCreateView.as_view(), name="registry-organizations"),
    path("organizations/mine/", MyOrganizationListView.as_view(), name="registry-my-organizations"),
    path("organizations/<uuid:public_id>/", OrganizationDetailView.as_view(), name="registry-organization-detail"),
    path("organizations/<uuid:public_id>/license-document/", OrganizationLicenseDocumentView.as_view(), name="registry-organization-license-document"),
    path("organizations/<uuid:public_id>/locations/", OrganizationLocationListCreateView.as_view(), name="registry-organization-locations"),
    path("organizations/<uuid:public_id>/status/", OrganizationStatusView.as_view(), name="registry-organization-status"),
    path("credentials/", PractitionerCredentialListCreateView.as_view(), name="registry-credentials"),
    path("credentials/<int:pk>/document/", PractitionerCredentialDocumentView.as_view(), name="registry-credential-document"),
    path("credentials/<int:pk>/verify/", PractitionerCredentialVerifyView.as_view(), name="registry-credential-verify"),
    path("practitioner-roles/", PractitionerRoleListCreateView.as_view(), name="registry-practitioner-roles"),
    path("care-relationships/", CareRelationshipListView.as_view(), name="registry-care-relationships"),
]
