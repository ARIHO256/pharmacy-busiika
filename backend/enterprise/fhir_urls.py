from django.urls import path
from .fhir_views import (CapabilityStatementView, FHIRHistoryView, FHIRInstanceView, FHIRTypeView, FHIRVersionView, SmartConfigurationView, SmartJwksView, SmartTokenView)

urlpatterns = [
    path(".well-known/smart-configuration", SmartConfigurationView.as_view(), name="smart-configuration"),
    path(".well-known/jwks.json", SmartJwksView.as_view(), name="smart-jwks"),
    path("oauth/token", SmartTokenView.as_view(), name="smart-token"),
    path("metadata", CapabilityStatementView.as_view(), name="fhir-capability"),
    path("<str:resource_type>", FHIRTypeView.as_view(), name="fhir-type"),
    path("<str:resource_type>/<uuid:logical_id>", FHIRInstanceView.as_view(), name="fhir-instance"),
    path("<str:resource_type>/<uuid:logical_id>/_history", FHIRHistoryView.as_view(), name="fhir-history"),
    path("<str:resource_type>/<uuid:logical_id>/_history/<int:version_id>", FHIRVersionView.as_view(), name="fhir-version"),
]
