from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsRole, request_role
from accounts.roles import BOOKABLE_PROVIDER_ROLES, NOTIFICATION_ROLES

from .models import Conversation, Message, Notification, NotificationPreference
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    NotificationSerializer,
    NotificationPreferenceSerializer,
)


class ConversationsView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", *sorted(BOOKABLE_PROVIDER_ROLES)]

    def get(self, request):
        conversations = Conversation.objects.filter(
            Q(patient=request.user) | Q(doctor=request.user)
        )
        serializer = ConversationSerializer(
            conversations, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request):
        if request_role(request) == "patient":
            doctor_id = request.data.get("doctor_id")
            if not doctor_id:
                return Response({"detail": "doctor_id is required"}, status=400)
            doctor = User.objects.filter(id=doctor_id, role__in=BOOKABLE_PROVIDER_ROLES, is_verified=True, is_active=True).first()
            if doctor is None:
                return Response({"detail": "Verified healthcare professional not found"}, status=404)
            patient = request.user
        else:
            patient_id = request.data.get("patient_id")
            if not patient_id:
                return Response({"detail": "patient_id is required"}, status=400)
            patient = User.objects.filter(id=patient_id, role="patient").first()
            if patient is None:
                return Response({"detail": "Patient not found"}, status=404)
            doctor = request.user

        appointment = None
        appointment_id = request.data.get("appointment_id")
        if appointment_id:
            from appointments.models import Appointment

            appointment = Appointment.objects.filter(id=appointment_id).first()

        conversation, created = Conversation.objects.get_or_create(
            patient=patient, doctor=doctor, defaults={"appointment": appointment}
        )
        serializer = ConversationSerializer(conversation, context={"request": request})
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MessagesView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", *sorted(BOOKABLE_PROVIDER_ROLES)]

    def _get_conversation(self, request, pk):
        conversation = Conversation.objects.filter(pk=pk).first()
        if conversation is None:
            return None, Response({"detail": "Conversation not found"}, status=404)
        if request.user not in (conversation.patient, conversation.doctor):
            return None, Response({"detail": "Not a participant"}, status=403)
        return conversation, None

    def get(self, request, pk):
        conversation, error = self._get_conversation(request, pk)
        if error:
            return error
        messages = conversation.messages.select_related("sender")
        # mark incoming messages read for the requester
        messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        serializer = MessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request, pk):
        conversation, error = self._get_conversation(request, pk)
        if error:
            return error
        text = request.data.get("text", "") or ""
        attachment = request.FILES.get("attachment")
        if not text.strip() and attachment is None:
            return Response(
                {"detail": "text or attachment is required"}, status=400
            )
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            attachment=attachment,
        )
        serializer = MessageSerializer(message, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


ALL_ROLES = sorted(NOTIFICATION_ROLES)


class NotificationsView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ALL_ROLES

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).prefetch_related("deliveries")
        unread = request.query_params.get("unread")
        kind = request.query_params.get("kind")
        if unread in {"1", "true", "yes"}:
            notifications = notifications.filter(is_read=False)
        if kind:
            notifications = notifications.filter(kind=kind)
        try:
            limit = min(max(int(request.query_params.get("limit", 50)), 1), 200)
        except (TypeError, ValueError):
            limit = 50
        rows = list(notifications[:limit])
        return Response(
            {
                "results": NotificationSerializer(rows, many=True).data,
                "unread_count": Notification.objects.filter(user=request.user, is_read=False).count(),
            }
        )


class NotificationReadView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ALL_ROLES

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ALL_ROLES

    def post(self, request):
        now = timezone.now()
        count = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True, read_at=now
        )
        return Response({"updated": count, "unread_count": 0})


class NotificationPreferencesView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ALL_ROLES

    def get_object(self, request):
        preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return preference

    def get(self, request):
        return Response(NotificationPreferenceSerializer(self.get_object(request)).data)

    def patch(self, request):
        preference = self.get_object(request)
        serializer = NotificationPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(NotificationPreferenceSerializer(serializer.save()).data)


class VideoRoomView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", *sorted(BOOKABLE_PROVIDER_ROLES)]

    def get(self, request, pk):
        from appointments.models import Appointment

        appointment = Appointment.objects.filter(pk=pk).first()
        if appointment is None:
            return Response({"detail": "Appointment not found"}, status=404)
        participant = request.user in (appointment.patient, appointment.doctor)
        if not participant and request_role(request) == "patient":
            from accounts.models import PatientRelationship
            from django.db.models import Q
            participant = PatientRelationship.objects.filter(
                caregiver=request.user, patient=appointment.patient,
                status=PatientRelationship.Status.ACTIVE, can_book=True,
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).exists()
        if not participant:
            return Response({"detail": "Not a participant"}, status=403)
        if appointment.status != "confirmed":
            return Response(
                {"detail": "Appointment is not confirmed"}, status=400
            )
        try:
            from enterprise.services import create_telemedicine_session
            from enterprise.serializers import TelemedicineSessionSerializer
            session = create_telemedicine_session(appointment, request.query_params.get("provider") or None)
            is_host = request.user.id == appointment.doctor_id
            payload = TelemedicineSessionSerializer(session).data
            payload.update({
                "room": session.external_id,
                "url": session.host_url if is_host else session.join_url,
                "websocket_url": f"/ws/telemedicine/{session.public_id}/",
                "is_host": is_host,
                "recording_consent_required": session.recording_consent_required,
            })
            return Response(payload)
        except Exception as exc:
            return Response({"detail": f"Telemedicine session could not be created: {exc}"}, status=503)


class DeviceRegistrationView(APIView):
    def get(self, request):
        from .models import DeviceRegistration
        from .serializers import DeviceRegistrationSerializer
        return Response(DeviceRegistrationSerializer(DeviceRegistration.objects.filter(user=request.user), many=True).data)

    def post(self, request):
        from .models import DeviceRegistration
        from .serializers import DeviceRegistrationSerializer
        serializer = DeviceRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row, _ = DeviceRegistration.objects.update_or_create(
            token=serializer.validated_data["token"],
            defaults={
                "user": request.user,
                "platform": serializer.validated_data["platform"],
                "device_name": serializer.validated_data.get("device_name", ""),
                "active": True,
            },
        )
        return Response(DeviceRegistrationSerializer(row).data, status=201)

    def delete(self, request, pk):
        from .models import DeviceRegistration
        row = get_object_or_404(DeviceRegistration, pk=pk, user=request.user)
        row.active = False
        row.save(update_fields=["active"])
        return Response(status=204)


class NotificationTemplateAdminView(APIView):
    def get(self, request, pk=None):
        from .models import NotificationTemplate
        from .serializers import NotificationTemplateSerializer
        if request_role(request) != "admin":
            return Response({"detail": "Administrator access required."}, status=403)
        if pk:
            return Response(NotificationTemplateSerializer(get_object_or_404(NotificationTemplate, pk=pk)).data)
        return Response(NotificationTemplateSerializer(NotificationTemplate.objects.all(), many=True).data)

    def post(self, request, pk=None):
        from .models import NotificationTemplate
        from .serializers import NotificationTemplateSerializer
        if request_role(request) != "admin":
            return Response({"detail": "Administrator access required."}, status=403)
        instance = get_object_or_404(NotificationTemplate, pk=pk) if pk else None
        serializer = NotificationTemplateSerializer(instance, data=request.data, partial=bool(instance))
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        return Response(NotificationTemplateSerializer(row).data, status=200 if instance else 201)


class NotificationBroadcastView(APIView):
    def post(self, request):
        from accounts.models import User
        from registry.models import Organization
        from workforce.models import StaffMembership
        from .services import notify
        if request_role(request) != "admin":
            return Response({"detail": "Administrator access required."}, status=403)
        title = str(request.data.get("title", "")).strip()
        body = str(request.data.get("body", "")).strip()
        if not title or not body:
            return Response({"detail": "title and body are required."}, status=400)
        users = User.objects.filter(is_active=True)
        role = request.data.get("role")
        if role:
            users = users.filter(role=role)
        organization_id = request.data.get("organization_id")
        if organization_id:
            member_ids = StaffMembership.objects.filter(organization_id=organization_id, status="active").values_list("user_id", flat=True)
            organization = Organization.objects.filter(pk=organization_id).first()
            owner_id = organization.owner_id if organization else None
            users = users.filter(Q(id__in=member_ids) | Q(id=owner_id))
        user_ids = request.data.get("user_ids") or []
        if user_ids:
            users = users.filter(id__in=user_ids)
        count = 0
        for user in users.iterator():
            notify(
                user,
                title,
                body,
                kind=request.data.get("kind", "announcement"),
                priority=request.data.get("priority", "normal"),
                action_url=request.data.get("action_url", ""),
                channels=request.data.get("channels") or None,
                metadata={"broadcast": True, "created_by": request.user.id},
            )
            count += 1
        return Response({"queued": count}, status=201)


class NotificationDeliveryCallbackView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request, channel):
        import secrets
        from django.conf import settings
        from .models import NotificationDelivery
        configured = getattr(settings, "NOTIFICATION_CALLBACK_SECRET", "")
        supplied = request.headers.get("X-Notification-Secret", "")
        if not configured or not secrets.compare_digest(configured, supplied):
            return Response({"detail": "Invalid callback signature."}, status=403)
        reference = str(request.data.get("provider_reference", ""))
        delivery = NotificationDelivery.objects.filter(provider_reference=reference, channel=channel).first()
        if not delivery:
            return Response({"detail": "Delivery not found."}, status=404)
        incoming = str(request.data.get("status", "")).lower()
        mapped = {
            "delivered": NotificationDelivery.Status.DELIVERED,
            "sent": NotificationDelivery.Status.SENT,
            "failed": NotificationDelivery.Status.FAILED,
            "rejected": NotificationDelivery.Status.FAILED,
        }.get(incoming)
        if not mapped:
            return Response({"detail": "Unsupported delivery status."}, status=400)
        delivery.status = mapped
        if mapped == NotificationDelivery.Status.DELIVERED:
            delivery.sent_at = delivery.sent_at or timezone.now()
        if mapped == NotificationDelivery.Status.FAILED:
            delivery.last_error = str(request.data.get("error", "Provider rejected delivery"))
        delivery.save(update_fields=["status", "sent_at", "last_error"])
        return Response({"updated": True})
