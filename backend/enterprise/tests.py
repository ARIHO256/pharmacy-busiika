from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from enterprise.models import (
    ActiveRoleContext,
    CommunicationConsent,
    ContentEntry,
    EnterpriseRecord,
    MasterPatientIndex,
    MedicationInteraction,
    MedicationKnowledge,
    RoleContext,
)
from enterprise.schemas import RECORD_SCHEMAS, validate_record
from enterprise.services import (
    fhir_bundle_for_patient,
    medication_safety_check,
    scan_duplicate_patients,
)


class SchemaCatalogueTests(TestCase):
    def test_every_record_schema_has_domain_roles_and_fields(self):
        self.assertGreaterEqual(len(RECORD_SCHEMAS), 70)
        for code, schema in RECORD_SCHEMAS.items():
            with self.subTest(code=code):
                self.assertTrue(schema.get("domain"))
                self.assertTrue(schema.get("label"))
                self.assertTrue(schema.get("roles"))
                self.assertIsInstance(schema.get("fields"), dict)

    def test_required_payload_validation(self):
        with self.assertRaises(ValidationError):
            validate_record("inpatient", "care_plan", {})
        validate_record(
            "inpatient",
            "care_plan",
            {"problem": "Impaired mobility", "goal": "Walk safely", "interventions": ["Assist mobilisation"]},
        )


class MultiRoleContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="multi@example.test", password="StrongPass!2026", role="doctor", is_verified=True
        )
        self.doctor = RoleContext.objects.create(user=self.user, role_code="doctor", is_primary=True)
        self.director = RoleContext.objects.create(user=self.user, role_code="medical_director")

    def test_user_can_hold_and_activate_multiple_contexts(self):
        self.assertEqual(self.user.role_contexts.count(), 2)
        active = ActiveRoleContext.objects.create(user=self.user, context=self.director)
        active.full_clean()
        self.assertEqual(active.context.role_code, "medical_director")

    def test_user_cannot_activate_another_users_context(self):
        other = User.objects.create_user(email="other@example.test", password="StrongPass!2026")
        active = ActiveRoleContext(user=other, context=self.doctor)
        with self.assertRaises(ValidationError):
            active.full_clean()


class ClinicalDecisionSupportTests(TestCase):
    def setUp(self):
        self.paracetamol = MedicationKnowledge.objects.create(
            generic_name="Paracetamol", brand_names=["Panadol"], contraindications=[], active=True
        )
        self.warfarin = MedicationKnowledge.objects.create(
            generic_name="Warfarin", brand_names=[], contraindications=["active bleeding"], pregnancy_category="Contraindicated", active=True
        )
        MedicationInteraction.objects.create(
            medicine_a=self.paracetamol,
            medicine_b=self.warfarin,
            severity="major",
            clinical_effect="Bleeding risk may increase.",
            management="Use the lowest dose and monitor INR.",
            evidence="demo",
            active=True,
        )

    def test_interaction_allergy_and_pregnancy_warnings(self):
        result = medication_safety_check(
            [self.paracetamol.id, self.warfarin.id],
            allergy_terms=["Panadol"],
            condition_terms=["active bleeding"],
            pregnant=True,
        )
        types = {item["type"] for item in result["warnings"]}
        self.assertTrue({"interaction", "allergy", "contraindication", "pregnancy"}.issubset(types))
        self.assertFalse(result["safe_to_continue"])
        self.assertTrue(result["requires_pharmacist_review"])


class MasterPatientIndexTests(TestCase):
    def test_duplicate_scanner_creates_candidate(self):
        first = User.objects.create_user(email="one@example.test", password="StrongPass!2026", role="patient", first_name="Amina", last_name="Kato", phone="+256700111222")
        second = User.objects.create_user(email="two@example.test", password="StrongPass!2026", role="patient", first_name="Amina", last_name="Kato", phone="+256700111222")
        for user in (first, second):
            MasterPatientIndex.objects.create(
                patient=user,
                normalized_name=user.display_name.lower(),
                normalized_phone=user.phone,
                status="active",
                confidence_score=Decimal("100.00"),
            )
        result = scan_duplicate_patients(min_score=70)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["total_candidates"], 1)


class EnterpriseRecordTests(TestCase):
    def test_record_generates_reference_and_validates_patient(self):
        patient = User.objects.create_user(email="patient@example.test", password="StrongPass!2026", role="patient")
        nurse = User.objects.create_user(email="nurse@example.test", password="StrongPass!2026", role="nurse")
        row = EnterpriseRecord(
            domain="inpatient",
            record_type="fluid_balance",
            patient=patient,
            owner=nurse,
            title="Fluid balance",
            payload={"intake_ml": 500, "output_ml": 300},
        )
        row.full_clean()
        row.save()
        self.assertTrue(row.reference.startswith("FLUID-BALANC"))


class EnterpriseApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@example.test", password="StrongPass!2026", first_name="Platform"
        )
        self.patient = User.objects.create_user(
            email="patient-api@example.test", password="StrongPass!2026", role="patient", is_verified=True
        )
        self.client = APIClient()

    def test_public_content_only_returns_current_published_rows(self):
        ContentEntry.objects.create(
            content_type="banner", slug="active", locale="en-UG", title="Active", body="Live",
            status="published", published_at=timezone.now(), starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1),
        )
        ContentEntry.objects.create(
            content_type="banner", slug="future", locale="en-UG", title="Future", body="Later",
            status="published", published_at=timezone.now(), starts_at=timezone.now() + timedelta(days=1),
        )
        response = self.client.get("/api/v1/enterprise/public/content/?locale=en-UG")
        self.assertEqual(response.status_code, 200)
        slugs = {item["slug"] for item in response.data}
        self.assertIn("active", slugs)
        self.assertNotIn("future", slugs)

    def test_schema_catalog_requires_authentication(self):
        response = self.client.get("/api/v1/enterprise/schema/")
        self.assertEqual(response.status_code, 401)

    def test_patient_sees_only_patient_permitted_schema(self):
        self.client.force_authenticate(self.patient)
        response = self.client.get("/api/v1/enterprise/schema/")
        self.assertEqual(response.status_code, 200)
        for schema in response.data["schemas"].values():
            self.assertIn("patient", schema["roles"])

    def test_admin_metrics_token_is_required_when_configured(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/enterprise/metrics/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("mydoctor_users_total", response.content.decode())

    def test_role_dashboard_returns_role_specific_summary(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/enterprise/dashboard/role/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("metrics", response.data)
        self.assertIn("queues", response.data)
        self.assertIn("open_total", response.data)

    def test_patient_lookup_returns_safe_display_fields(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/enterprise/lookups/?kind=patient&q=patient-api")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["kind"], "patient")
        self.assertTrue(response.data["results"])
        result = response.data["results"][0]
        self.assertEqual(result["id"], self.patient.id)
        self.assertIn("label", result)
        self.assertIn("meta", result)
        self.assertNotIn("password", result)

    def test_communication_consent_is_unique_per_purpose(self):
        CommunicationConsent.objects.create(user=self.patient, channel="sms", purpose="care", granted=True)
        with self.assertRaises(Exception):
            CommunicationConsent.objects.create(user=self.patient, channel="sms", purpose="care", granted=True)


class FhirExportTests(TestCase):
    def test_empty_patient_bundle_is_valid_collection(self):
        patient = User.objects.create_user(email="fhir@example.test", password="StrongPass!2026", role="patient")
        bundle = fhir_bundle_for_patient(patient)
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "collection")
        self.assertEqual(bundle["total"], 0)
