from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsRole
from accounts.roles import NOTIFICATION_ROLES

from .models import Conversation, Message, Notification, NotificationPreference
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    NotificationSerializer,
    NotificationPreferenceSerializer,
)


class ConversationsView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor"]

    def get(self, request):
        conversations = Conversation.objects.filter(
            Q(patient=request.user) | Q(doctor=request.user)
        )
        serializer = ConversationSerializer(
            conversations, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request):
        if request.user.role == "patient":
            doctor_id = request.data.get("doctor_id")
            if not doctor_id:
                return Response({"detail": "doctor_id is required"}, status=400)
            doctor = User.objects.filter(id=doctor_id, role="doctor").first()
            if doctor is None:
                return Response({"detail": "Doctor not found"}, status=404)
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
    allowed_roles = ["patient", "doctor"]

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
        changed = messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        messages.filter(read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now(), delivered_at=timezone.now())
        if changed:
            from .realtime import broadcast
            broadcast(conversation.pk, "message.receipt")
        serializer = MessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request, pk):
        conversation, error = self._get_conversation(request, pk)
        if error:
            return error
        text = request.data.get("text", "") or ""
        attachment = request.FILES.get("attachment")
        if len(text) > 20000:
            return Response({"detail": "Message exceeds the size limit."}, status=400)
        client_id = request.data.get("client_id") or None
        if client_id:
            from rest_framework import serializers
            client_id = serializers.UUIDField().run_validation(client_id)
            Conversation.objects.select_for_update().get(pk=conversation.pk)
            previous = Message.objects.filter(conversation=conversation, sender=request.user, client_id=client_id).first()
            if previous:
                if previous.text != text:
                    return Response({"detail": "Message ID was reused for different text."}, status=409)
                return Response(MessageSerializer(previous, context={"request": request}).data)
        if not text.strip() and attachment is None:
            return Response(
                {"detail": "text or attachment is required"}, status=400
            )
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            attachment=attachment,
            client_id=client_id,
        )
        from .realtime import broadcast
        broadcast(conversation.pk, "message.created", message.pk)
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
    allowed_roles = ["patient", "doctor"]

    def get(self, request, pk):
        from operations.integration_views import video_join
        return Response(video_join(request.user, pk))


class MessageSyncView(MessagesView):
    def get(self, request, pk):
        from rest_framework import serializers
        conversation, error = self._get_conversation(request, pk)
        if error:
            return error
        after = serializers.IntegerField(min_value=0).run_validation(request.query_params.get("after", 0))
        rows = list(conversation.messages.filter(pk__gt=after).select_related("sender").order_by("id")[:201])
        page = rows[:200]
        return Response({"results": MessageSerializer(page, many=True, context={"request": request}).data,
                         "cursor": page[-1].pk if page else after, "has_more": len(rows) > 200})

    def post(self, request, pk):
        from rest_framework import serializers
        from .realtime import broadcast
        conversation, error = self._get_conversation(request, pk)
        if error:
            return error
        through_id = serializers.IntegerField(min_value=1).run_validation(request.data.get("through_id"))
        phase = serializers.ChoiceField(choices=["delivered", "read"]).run_validation(request.data.get("phase"))
        now = timezone.now()
        rows = conversation.messages.filter(pk__lte=through_id).exclude(sender=request.user)
        rows.filter(delivered_at__isnull=True).update(delivered_at=now)
        if phase == "read":
            rows.filter(read_at__isnull=True).update(is_read=True, read_at=now)
        broadcast(conversation.pk, "message.receipt", through_id)
        return Response({"acknowledged": True})

