import datetime
from unittest import skipUnless

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Review

User = get_user_model()

try:
    from appointments.models import Appointment

    HAS_APPOINTMENTS = True
except Exception:  # pragma: no cover
    Appointment = None
    HAS_APPOINTMENTS = False

try:
    from accounts.models import DoctorProfile

    HAS_PROFILES = True
except Exception:  # pragma: no cover
    DoctorProfile = None
    HAS_PROFILES = False


def make_user(email, role, **kw):
    return User.objects.create_user(email=email, password="pass1234", role=role, **kw)


@skipUnless(HAS_APPOINTMENTS, "appointments app not available in this worktree")
class ReviewFlowTests(APITestCase):
    def setUp(self):
        self.doctor = make_user("doc@example.com", "doctor", first_name="Greg")
        self.patient = make_user("pat@example.com", "patient", first_name="Pat")
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            type="online",
            status="completed",
        )

    def _create_review(self, rating=5):
        self.client.force_authenticate(self.patient)
        return self.client.post(
            f"/api/appointments/{self.appointment.id}/review/",
            {"rating": rating, "comment": "great"},
            format="json",
        )

    def test_patient_can_review_completed_appointment_once(self):
        resp = self._create_review()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["rating"], 5)
        # second review for same appointment rejected
        resp2 = self._create_review()
        self.assertEqual(resp2.status_code, 400)

    def test_review_requires_completed_appointment(self):
        self.appointment.status = "confirmed"
        self.appointment.save(update_fields=["status"])
        resp = self._create_review()
        self.assertEqual(resp.status_code, 400)

    def test_public_doctor_reviews_list(self):
        self._create_review(rating=4)
        self.client.force_authenticate(user=None)
        resp = self.client.get(f"/api/doctors/{self.doctor.id}/reviews/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["patient"], "Pat")
        self.assertEqual(resp.data[0]["rating"], 4)

    @skipUnless(HAS_PROFILES, "accounts.DoctorProfile not available in this worktree")
    def test_review_updates_average_rating(self):
        DoctorProfile.objects.create(user=self.doctor, average_rating=0)
        self._create_review(rating=4)
        profile = DoctorProfile.objects.get(user=self.doctor)
        self.assertEqual(float(profile.average_rating), 4.0)

        # second appointment + review -> average of 4 and 2 = 3
        appt2 = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 30),
            type="offline",
            status="completed",
        )
        self.client.force_authenticate(self.patient)
        self.client.post(
            f"/api/appointments/{appt2.id}/review/",
            {"rating": 2, "comment": "meh"},
            format="json",
        )
        profile.refresh_from_db()
        self.assertEqual(float(profile.average_rating), 3.0)


@skipUnless(HAS_APPOINTMENTS, "appointments app not available in this worktree")
class ReviewModerationTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", "admin")
        self.doctor = make_user("mod-doc@example.com", "doctor", first_name="Greg")
        self.patient = make_user("mod-pat@example.com", "patient", first_name="Pat")
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 30),
            type="online",
            status="completed",
        )

    def _create_review(self, rating=4):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            f"/api/appointments/{self.appointment.id}/review/",
            {"rating": rating, "comment": "good"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        return resp.data["id"]

    def _public_list(self):
        self.client.force_authenticate(user=None)
        return self.client.get(f"/api/doctors/{self.doctor.id}/reviews/")

    def test_admin_can_hide_and_unhide_review(self):
        review_id = self._create_review()
        self.client.force_authenticate(self.admin)

        resp = self.client.post(
            f"/api/admin/reviews/{review_id}/action/",
            {"action": "hide", "note": "abusive language"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["status"], "hidden")
        self.assertEqual(resp.data["moderated_by"], self.admin.id)
        self.assertEqual(resp.data["moderation_note"], "abusive language")
        review = Review.objects.get(pk=review_id)
        self.assertIsNotNone(review.moderated_at)

        # hidden review leaves the public listing
        resp = self._public_list()
        self.assertEqual(len(resp.data), 0)

        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/admin/reviews/{review_id}/action/",
            {"action": "unhide"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "visible")
        resp = self._public_list()
        self.assertEqual(len(resp.data), 1)

    def test_flagged_review_excluded_from_public_list_and_rating(self):
        review_id = self._create_review(rating=4)
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/admin/reviews/{review_id}/action/",
            {"action": "flag"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["status"], "flagged")
        self.assertEqual(len(self._public_list().data), 0)

    @skipUnless(HAS_PROFILES, "accounts.DoctorProfile not available in this worktree")
    def test_hidden_review_excluded_from_average_rating(self):
        DoctorProfile.objects.create(user=self.doctor, average_rating=0)
        review_id = self._create_review(rating=4)
        profile = DoctorProfile.objects.get(user=self.doctor)
        self.assertEqual(float(profile.average_rating), 4.0)

        self.client.force_authenticate(self.admin)
        self.client.post(
            f"/api/admin/reviews/{review_id}/action/",
            {"action": "hide"},
            format="json",
        )
        profile.refresh_from_db()
        self.assertEqual(float(profile.average_rating), 0.0)

    def test_moderation_requires_admin_and_valid_action(self):
        review_id = self._create_review()
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            f"/api/admin/reviews/{review_id}/action/",
            {"action": "hide"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/admin/reviews/{review_id}/action/",
            {"action": "delete"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
