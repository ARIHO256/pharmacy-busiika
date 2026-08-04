import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from appointments.models import Appointment

from .models import Notification
from .services import notify

PASSWORD = "testpass123"


def make_user(email, role, first="First", last="Last"):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=role, first_name=first, last_name=last
    )


class CommunicationApiTests(TestCase):
    def setUp(self):
        self.patient = make_user("patient@example.com", "patient", "Pat", "One")
        self.doctor = make_user("doctor@example.com", "doctor", "Doc", "Two")
        self.other = make_user("other@example.com", "patient", "Oth", "Er")
        self.client = APIClient()

    def auth(self, user):
        response = self.client.post(
            "/api/auth/token/", {"email": user.email, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )

    def test_conversation_create_get_or_create_and_messages(self):
        self.auth(self.patient)
        response = self.client.post(
            "/api/conversations/", {"doctor_id": self.doctor.id}
        )
        self.assertEqual(response.status_code, 201)
        conversation_id = response.data["id"]
        self.assertEqual(response.data["other_party_name"], "Doc Two")

        # get_or_create: second POST returns the same conversation
        response = self.client.post(
            "/api/conversations/", {"doctor_id": self.doctor.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], conversation_id)

        # send a message
        response = self.client.post(
            f"/api/conversations/{conversation_id}/messages/", {"text": "Hello doc"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["text"], "Hello doc")

        # doctor sees unread count, then GET marks messages read
        self.auth(self.doctor)
        response = self.client.get("/api/conversations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["unread_count"], 1)
        self.assertEqual(response.data[0]["last_message"]["text"], "Hello doc")

        response = self.client.get(
            f"/api/conversations/{conversation_id}/messages/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertTrue(response.data[0]["is_read"])

        # non-participant cannot read messages
        self.auth(self.other)
        response = self.client.get(
            f"/api/conversations/{conversation_id}/messages/"
        )
        self.assertEqual(response.status_code, 403)

    def test_notifications_list_and_read(self):
        notify(self.patient, "Hello", "Body text", kind="general")
        notify(self.patient, "Reminder", "Second", kind="reminder")
        self.auth(self.patient)
        response = self.client.get("/api/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 2)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["results"][0]["title"], "Reminder")  # newest first

        notification_id = response.data["results"][0]["id"]
        response = self.client.post(f"/api/notifications/{notification_id}/read/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])
        self.assertTrue(
            Notification.objects.get(id=notification_id).is_read
        )

    def test_video_room_requires_confirmed_and_participant(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=datetime.date(2030, 1, 1),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 30),
            status="confirmed",
        )
        self.auth(self.patient)
        response = self.client.get(
            f"/api/appointments/{appointment.id}/video-room/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["room"], f"mydoctor-{appointment.id}")
        self.assertEqual(
            response.data["url"], f"https://meet.jit.si/mydoctor-{appointment.id}"
        )

        # outsider rejected
        self.auth(self.other)
        response = self.client.get(
            f"/api/appointments/{appointment.id}/video-room/"
        )
        self.assertEqual(response.status_code, 403)

        # unconfirmed appointment rejected
        appointment.status = "pending"
        appointment.save()
        self.auth(self.doctor)
        response = self.client.get(
            f"/api/appointments/{appointment.id}/video-room/"
        )
        self.assertEqual(response.status_code, 400)


    def test_notification_preferences_create_delivery_jobs(self):
        from .models import NotificationDelivery, NotificationPreference

        NotificationPreference.objects.create(
            user=self.patient, in_app_enabled=True, email_enabled=True, sms_enabled=False
        )
        notification = notify(
            self.patient,
            "Payment receipt ready",
            "Your receipt can be viewed in MyDoctor.",
            kind="payment",
            channels=["in_app", "email", "sms"],
        )
        channels = set(notification.deliveries.values_list("channel", flat=True))
        self.assertEqual(channels, {"in_app", "email"})
        self.assertTrue(
            NotificationDelivery.objects.filter(
                notification=notification, channel="email", status="pending"
            ).exists()
        )

        self.auth(self.patient)
        response = self.client.patch(
            "/api/notifications/preferences/",
            {"sms_enabled": True, "quiet_hours_start": "22:00", "quiet_hours_end": "06:00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["sms_enabled"])
