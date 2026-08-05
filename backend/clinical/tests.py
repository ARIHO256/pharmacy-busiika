import datetime

from rest_framework.test import APITestCase

from accounts.models import DoctorProfile, ProfileStatus, User
from appointments.models import Appointment
from governance.models import Consent

from .models import ClinicalEncounter, Observation


class ClinicalApiTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient@clinical.test", password="pass12345", role="patient"
        )
        self.doctor = User.objects.create_user(
            email="doctor@clinical.test", password="pass12345", role="doctor", is_verified=True
        )
        DoctorProfile.objects.create(user=self.doctor, status=ProfileStatus.VERIFIED)
        self.other_doctor = User.objects.create_user(
            email="other@clinical.test", password="pass12345", role="doctor"
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            type="online",
            status="confirmed",
            reason="Persistent headache",
        )
        Consent.objects.create(
            patient=self.patient,
            granted_to=self.doctor,
            consent_type="treatment",
            purpose="treatment",
            data_categories=["clinical_record"],
        )

    def test_patient_can_create_and_read_structured_allergy(self):
        self.client.force_authenticate(self.patient)
        response = self.client.post(
            "/api/clinical/allergies/",
            {"substance": "Penicillin", "reaction": "Rash", "severity": "moderate"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        response = self.client.get("/api/clinical/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["allergies"][0]["substance"], "Penicillin")

    def test_doctor_can_create_and_finalize_encounter(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            "/api/clinical/encounters/",
            {
                "appointment": self.appointment.id,
                "assessment": "Tension headache",
                "treatment_plan": "Hydration, rest and analgesia",
                "safety_net_advice": "Seek urgent care for weakness or confusion",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        encounter_id = response.data["id"]
        response = self.client.post(f"/api/clinical/encounters/{encounter_id}/finalize/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], ClinicalEncounter.Status.FINAL)
        self.assertEqual(response.data["version"], 1)

    def test_unrelated_doctor_is_denied(self):
        self.client.force_authenticate(self.other_doctor)
        response = self.client.get(
            f"/api/clinical/summary/?patient_id={self.patient.id}"
        )
        self.assertEqual(response.status_code, 403)

    def test_doctor_can_record_vital_observation(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            f"/api/clinical/observations/?patient_id={self.patient.id}",
            {
                "patient_id": self.patient.id,
                "category": "vital_signs",
                "code": "systolic-bp",
                "display": "Systolic blood pressure",
                "value_numeric": "135",
                "unit": "mmHg",
                "interpretation": "high",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Observation.objects.count(), 1)

    def test_final_encounter_can_only_change_through_versioned_amendment(self):
        self.client.force_authenticate(self.doctor)
        created = self.client.post(
            "/api/clinical/encounters/",
            {
                "appointment": self.appointment.id,
                "assessment": "Initial assessment",
                "treatment_plan": "Initial plan",
            },
            format="json",
        )
        encounter_id = created.data["id"]
        finalized = self.client.post(f"/api/clinical/encounters/{encounter_id}/finalize/")
        self.assertEqual(finalized.status_code, 200)
        blocked = self.client.patch(
            f"/api/clinical/encounters/{encounter_id}/",
            {"assessment": "Silent overwrite"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 409)
        amended = self.client.post(
            f"/api/clinical/encounters/{encounter_id}/amend/",
            {"reason": "Correction after reviewing the consultation", "assessment": "Corrected assessment"},
            format="json",
        )
        self.assertEqual(amended.status_code, 200, amended.data)
        self.assertEqual(amended.data["status"], ClinicalEncounter.Status.AMENDED)
        self.assertEqual(amended.data["version"], 2)
        self.assertEqual(len(amended.data["revisions"]), 2)


class ClosedLoopReferralTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(email="ref.patient@test.local", password="pass12345", role="patient")
        self.referrer = User.objects.create_user(email="referrer@test.local", password="pass12345", role="doctor", is_verified=True)
        self.receiver = User.objects.create_user(email="receiver@test.local", password="pass12345", role="doctor", is_verified=True)
        DoctorProfile.objects.create(user=self.referrer, status=ProfileStatus.VERIFIED)
        DoctorProfile.objects.create(user=self.receiver, status=ProfileStatus.VERIFIED)
        self.appointment = Appointment.objects.create(
            patient=self.patient, doctor=self.referrer, date=datetime.date.today(),
            start_time=datetime.time(11, 0), end_time=datetime.time(11, 30), status="confirmed",
        )
        Consent.objects.create(
            patient=self.patient, granted_to=self.referrer, consent_type="treatment",
            purpose="treatment", data_categories=["clinical_record"],
        )

    def test_receiver_accepts_and_closes_referral_with_feedback(self):
        self.client.force_authenticate(self.referrer)
        created = self.client.post(
            f"/api/clinical/referrals/?patient_id={self.patient.id}",
            {
                "target_provider": self.receiver.id,
                "target_specialty": "Internal medicine",
                "reason": "Persistent symptoms",
                "clinical_summary": "Stable but needs specialist review",
                "priority": "urgent",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        referral_id = created.data["id"]
        self.client.force_authenticate(self.receiver)
        accepted = self.client.post(f"/api/clinical/referrals/{referral_id}/action/", {"action": "accept"}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        started = self.client.post(f"/api/clinical/referrals/{referral_id}/action/", {"action": "start"}, format="json")
        self.assertEqual(started.status_code, 200, started.data)
        completed = self.client.post(
            f"/api/clinical/referrals/{referral_id}/action/",
            {"action": "complete", "outcome_summary": "Reviewed and adjusted the treatment plan."},
            format="json",
        )
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(completed.data["status"], "completed")
        self.assertEqual(len(completed.data["status_history"]), 4)


class FollowUpRecallTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="recall.patient@test.local", password="pass12345", role="patient"
        )
        self.doctor = User.objects.create_user(
            email="recall.doctor@test.local", password="pass12345", role="doctor", is_verified=True
        )
        DoctorProfile.objects.create(user=self.doctor, status=ProfileStatus.VERIFIED)

    def _encounter(self, follow_up_date, start_time=datetime.time(9, 0)):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=start_time,
            end_time=datetime.time(start_time.hour, start_time.minute + 30),
            status="completed",
        )
        return ClinicalEncounter.objects.create(
            appointment=appointment,
            patient=self.patient,
            doctor=self.doctor,
            status=ClinicalEncounter.Status.FINAL,
            assessment="Stable",
            treatment_plan="Review in clinic",
            follow_up_date=follow_up_date,
        )

    def test_recall_task_notifies_patient_and_dedupes_on_rerun(self):
        from communication.models import Notification

        from .tasks import send_follow_up_recalls

        encounter = self._encounter(datetime.date.today() + datetime.timedelta(days=2))
        result = send_follow_up_recalls()
        self.assertEqual(result["sent"], 1)
        notifications = Notification.objects.filter(user=self.patient, kind="follow_up_recall")
        self.assertEqual(notifications.count(), 1)
        notification = notifications.get()
        self.assertIn("follow-up", notification.title.lower())
        self.assertEqual(
            notification.metadata["dedupe_key"],
            f"follow_up:{encounter.pk}:{encounter.follow_up_date.isoformat()}",
        )
        # A rerun must not send a second reminder for the same encounter.
        rerun = send_follow_up_recalls()
        self.assertEqual(rerun["sent"], 0)
        self.assertEqual(notifications.count(), 1)

    def test_recall_task_ignores_encounters_outside_the_window(self):
        from communication.models import Notification

        from .tasks import send_follow_up_recalls

        self._encounter(datetime.date.today() + datetime.timedelta(days=10))
        self._encounter(datetime.date.today() - datetime.timedelta(days=1), datetime.time(10, 0))
        self._encounter(None, datetime.time(11, 0))
        result = send_follow_up_recalls()
        self.assertEqual(result["sent"], 0)
        self.assertFalse(
            Notification.objects.filter(user=self.patient, kind="follow_up_recall").exists()
        )
