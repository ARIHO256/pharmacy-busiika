from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.permissions import role_allowed
from clinical.services import can_access_patient
from enterprise.access import active_role, can_manage_platform
from enterprise.models import ActiveRoleContext, RoleContext
from governance.models import PrivilegedAccessGrant

User = get_user_model()


class ActiveRoleAuthorizationTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient.authorization@example.test", password="Pass!123456", role="patient", is_verified=True
        )
        self.worker = User.objects.create_user(
            email="worker.authorization@example.test", password="Pass!123456", role="receptionist", is_verified=True
        )
        self.context = RoleContext.objects.create(
            user=self.worker, role_code="records_officer", title="Medical records officer", is_primary=True
        )
        ActiveRoleContext.objects.update_or_create(user=self.worker, defaults={"context": self.context})

    def test_active_context_is_authoritative_over_registration_role(self):
        self.assertEqual(self.worker.role, "receptionist")
        self.assertEqual(active_role(self.worker), "records_officer")

    def test_superuser_does_not_silently_inherit_clinical_roles(self):
        admin = User.objects.create_superuser(email="root.authorization@example.test", password="Pass!123456")
        self.assertFalse(role_allowed("admin", ["doctor"], admin))
        self.assertTrue(role_allowed("admin", ["admin"], admin))

    def test_it_and_compliance_officers_are_not_platform_managers(self):
        for index, role in enumerate(("it_support", "compliance_officer")):
            user = User.objects.create_user(email=f"{role}{index}@example.test", password="Pass!123456", role=role)
            context = RoleContext.objects.create(user=user, role_code=role, is_primary=True)
            ActiveRoleContext.objects.update_or_create(user=user, defaults={"context": context})
            self.assertFalse(can_manage_platform(user), role)


class ControlledClinicalAccessTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient.clinical@example.test", password="Pass!123456", role="patient", is_verified=True
        )
        self.admin = User.objects.create_user(
            email="admin.clinical@example.test", password="Pass!123456", role="admin", is_verified=True, mfa_enabled=True
        )
        context = RoleContext.objects.create(user=self.admin, role_code="platform_super_admin", is_primary=True)
        ActiveRoleContext.objects.update_or_create(user=self.admin, defaults={"context": context})

    def test_administrator_has_no_standing_clinical_access(self):
        allowed, emergency, reason = can_access_patient(self.admin, self.patient)
        self.assertFalse(allowed)
        self.assertFalse(emergency)
        self.assertIn("patient-specific elevation", reason)

    def test_requester_cannot_approve_own_privileged_access(self):
        grant = PrivilegedAccessGrant.objects.create(
            requester=self.admin,
            patient=self.patient,
            purpose="clinical safety investigation",
            reason="Investigating a documented safety incident affecting this patient.",
            scopes=["patient_summary"],
        )
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post(
            reverse("privileged-access-decision", args=[grant.pk]),
            {"action": "approve", "duration_minutes": 20},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class JourneyApiBoundaryTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient.journey@example.test", password="Pass!123456", role="patient", is_verified=True
        )
        self.other_patient = User.objects.create_user(
            email="other.journey@example.test", password="Pass!123456", role="patient", is_verified=True
        )
        context = RoleContext.objects.create(user=self.patient, role_code="patient", is_primary=True)
        ActiveRoleContext.objects.update_or_create(user=self.patient, defaults={"context": context})
        self.client = APIClient()
        self.client.force_authenticate(self.patient)

    def test_read_only_page_rejects_generic_case_creation(self):
        response = self.client.post(
            reverse("journey-page-cases", args=["notification-inbox"]),
            {"title": "Fake notification"},
            format="json",
        )
        self.assertEqual(response.status_code, 405)

    def test_patient_cannot_create_a_workflow_for_an_unmanaged_patient(self):
        response = self.client.post(
            reverse("journey-page-cases", args=["consent-centre"]),
            {
                "title": "Unauthorized consent attempt",
                "patient": self.other_patient.id,
                "data": {"consent_type": "treatment", "purpose": "treatment"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class WorkflowCompletionContractTests(TestCase):
    def test_every_actionable_page_has_a_canonical_adapter(self):
        from journeys.definitions import MANIFEST, definition_for

        missing = []
        for slug in MANIFEST:
            definition = definition_for(slug)
            if definition.get("create_allowed", True) and not definition.get("adapter"):
                missing.append(slug)
        self.assertEqual(missing, [])

    def test_every_page_has_an_explicit_mode_and_source(self):
        from journeys.definitions import MANIFEST, definition_for

        invalid = []
        for slug in MANIFEST:
            definition = definition_for(slug)
            if not definition.get("page_mode") or not definition.get("canonical_source"):
                invalid.append(slug)
        self.assertEqual(invalid, [])


class OperationalActionTests(TestCase):
    def setUp(self):
        from journeys.models import OperationalAction

        self.OperationalAction = OperationalAction
        self.doctor = User.objects.create_user(
            email="doctor.operations@example.test", password="Pass!123456", role="doctor", is_verified=True
        )
        context = RoleContext.objects.create(user=self.doctor, role_code="doctor", is_primary=True)
        ActiveRoleContext.objects.update_or_create(user=self.doctor, defaults={"context": context})
        self.client = APIClient()
        self.client.force_authenticate(self.doctor)

    def test_generic_personalisation_page_creates_and_executes_canonical_action(self):
        response = self.client.post(
            reverse("journey-page-cases", args=["clinical-templates"]),
            {
                "data": {
                    "name": "Stable asthma review",
                    "content": {"sections": ["history", "examination", "plan"]},
                    "active": True,
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        public_id = response.data["public_id"]
        action = self.OperationalAction.objects.get(workflow_case__public_id=public_id)
        self.assertEqual(action.operation_code, "clinical-templates")
        self.assertEqual(action.state, self.OperationalAction.State.SUBMITTED)

        response = self.client.post(
            reverse("journey-case-actions", args=[public_id]),
            {"action": "activate", "note": "Reviewed for my own clinical workspace."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        action.refresh_from_db()
        self.assertEqual(action.state, self.OperationalAction.State.EXECUTED)
        self.assertIsNotNone(action.executed_at)
        self.assertTrue(action.effect_log)

    def test_page_data_exposes_operational_actions_not_unconfigured_shell(self):
        self.client.post(
            reverse("journey-page-cases", args=["clinical-templates"]),
            {"data": {"name": "Template", "content": {"body": "value"}, "active": True}},
            format="json",
        )
        response = self.client.get(reverse("journey-page-data", args=["clinical-templates"]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["configured"])
        self.assertEqual(response.data["kind"], "operational_actions")
        self.assertGreaterEqual(len(response.data["records"]), 1)


class ReleaseAcceptanceTests(TestCase):
    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.SimpleUploadedFile = SimpleUploadedFile
        self.admin = User.objects.create_user(
            email="release.admin@example.test", password="Pass!123456", role="admin", is_verified=True
        )
        context = RoleContext.objects.create(user=self.admin, role_code="platform_super_admin", is_primary=True)
        ActiveRoleContext.objects.update_or_create(user=self.admin, defaults={"context": context})
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_acceptance_requires_evidence_and_records_hash(self):
        payload = {
            "release_version": "2026.08.04",
            "environment": "production",
            "acceptance_type": "security",
            "status": "accepted",
            "reviewer_name": "Security Reviewer",
            "reviewer_title": "Security Lead",
            "reviewer_email": "security@example.test",
            "statement": "I reviewed the security evidence and accept this release gate.",
        }
        response = self.client.post(reverse("journey-release-acceptances"), payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        payload["evidence"] = self.SimpleUploadedFile("security-evidence.txt", b"signed security acceptance evidence")
        response = self.client.post(reverse("journey-release-acceptances"), payload, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["evidence_hash"])
        self.assertTrue(response.data["is_currently_accepted"])

    def test_readiness_remains_blocked_until_all_gate_types_are_accepted(self):
        response = self.client.get(
            reverse("journey-production-readiness"),
            {"release_version": "2026.08.04", "environment": "production"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["ready_for_promotion"])
        self.assertEqual(len(response.data["gates"]), 12)


class QualifiedReleaseReviewerTests(TestCase):
    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.SimpleUploadedFile = SimpleUploadedFile
        self.doctor = User.objects.create_user(
            email="qualified.doctor@example.test", password="Pass!123456", role="doctor", is_verified=True
        )
        context = RoleContext.objects.create(user=self.doctor, role_code="doctor", is_primary=True)
        ActiveRoleContext.objects.update_or_create(user=self.doctor, defaults={"context": context})
        self.client = APIClient(); self.client.force_authenticate(self.doctor)

    def test_qualified_reviewer_can_view_release_gates(self):
        response = self.client.get(reverse("journey-production-readiness"), {"release_version": "2026.08.04"})
        self.assertEqual(response.status_code, 200)

    def test_reviewer_can_sign_only_their_professional_gate(self):
        base = {
            "release_version": "2026.08.04", "environment": "production", "status": "accepted",
            "reviewer_name": "Dr Qualified Reviewer", "statement": "I completed the documented role workflow acceptance scenarios.",
            "evidence": self.SimpleUploadedFile("doctor-evidence.txt", b"signed doctor workflow evidence"),
        }
        allowed = self.client.post(reverse("journey-release-acceptances"), {**base, "acceptance_type": "doctor_workflow"}, format="multipart")
        self.assertEqual(allowed.status_code, 201, allowed.data)
        denied = self.client.post(reverse("journey-release-acceptances"), {
            **base, "acceptance_type": "finance_workflow",
            "evidence": self.SimpleUploadedFile("finance-evidence.txt", b"invalid cross-role evidence"),
        }, format="multipart")
        self.assertEqual(denied.status_code, 403)


class OrganizationIsolationTests(TestCase):
    def setUp(self):
        from registry.models import Organization

        self.org_a = Organization.objects.create(
            legal_name="Isolation Hospital A", organization_type=Organization.Type.HOSPITAL,
            status=Organization.Status.VERIFIED,
        )
        self.org_b = Organization.objects.create(
            legal_name="Isolation Hospital B", organization_type=Organization.Type.HOSPITAL,
            status=Organization.Status.VERIFIED,
        )
        self.manager_a = User.objects.create_user(
            email="manager.a@example.test", password="Pass!123456", role="facility_manager", is_verified=True
        )
        self.manager_b = User.objects.create_user(
            email="manager.b@example.test", password="Pass!123456", role="facility_manager", is_verified=True
        )
        for user, org in ((self.manager_a, self.org_a), (self.manager_b, self.org_b)):
            context = RoleContext.objects.create(
                user=user, organization=org, role_code="facility_manager", is_primary=True
            )
            ActiveRoleContext.objects.update_or_create(user=user, defaults={"context": context})

    def test_operational_actions_are_isolated_by_active_organization(self):
        client_a = APIClient(); client_a.force_authenticate(self.manager_a)
        response = client_a.post(
            reverse("journey-page-cases", args=["room-management"]),
            {"data": {"operation_type": "create_room", "details": "Create room A-101", "configuration": {"room": "A-101"}}},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        client_b = APIClient(); client_b.force_authenticate(self.manager_b)
        response_b = client_b.get(reverse("journey-page-data", args=["room-management"]))
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_b.data["records"], [])

    def test_role_context_cannot_be_activated_for_another_user(self):
        from enterprise.models import ActiveRoleContext
        foreign_context = self.manager_a.role_contexts.first()
        activation = ActiveRoleContext(user=self.manager_b, context=foreign_context)
        with self.assertRaises(Exception):
            activation.full_clean()


class PrivilegedAccessExpiryTests(TestCase):
    def test_expired_grant_never_restores_standing_admin_access(self):
        from django.utils import timezone
        from datetime import timedelta
        from clinical.services import can_access_patient

        patient = User.objects.create_user(email="expired.patient@example.test", password="Pass!123456", role="patient")
        admin = User.objects.create_user(email="expired.admin@example.test", password="Pass!123456", role="admin", mfa_enabled=True)
        context = RoleContext.objects.create(user=admin, role_code="platform_super_admin", is_primary=True)
        ActiveRoleContext.objects.update_or_create(user=admin, defaults={"context": context})
        reviewer = User.objects.create_user(email="expired.reviewer@example.test", password="Pass!123456", role="clinical_safety_admin")
        PrivilegedAccessGrant.objects.create(
            requester=admin, patient=patient, purpose="safety review",
            reason="Expired safety review access for automated isolation testing.",
            scopes=["patient_summary"], status=PrivilegedAccessGrant.Status.ACTIVE,
            approved_by=reviewer, approved_at=timezone.now() - timedelta(hours=2),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        allowed, _, reason = can_access_patient(admin, patient)
        self.assertFalse(allowed)
        self.assertIn("patient-specific elevation", reason)
