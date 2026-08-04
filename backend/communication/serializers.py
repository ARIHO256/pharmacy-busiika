from rest_framework import serializers

from config.uploads import validate_chat_attachment

from .models import (
    Conversation,
    Message,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)


def _display_name(user):
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    attachment = serializers.FileField(required=False, allow_null=True, validators=[validate_chat_attachment])

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "sender_name",
            "text",
            "attachment",
            "created_at",
            "is_read",
        ]
        read_only_fields = ["id", "conversation", "sender", "created_at", "is_read"]

    def get_sender_name(self, obj):
        return _display_name(obj.sender)


class ConversationSerializer(serializers.ModelSerializer):
    other_party_id = serializers.SerializerMethodField()
    other_party_name = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "patient",
            "doctor",
            "appointment",
            "other_party_id",
            "other_party_name",
            "last_message",
            "unread_count",
            "created_at",
        ]

    def _other(self, obj):
        request = self.context.get("request")
        if request is not None and request.user == obj.patient:
            return obj.doctor
        return obj.patient

    def get_other_party_id(self, obj):
        return self._other(obj).id

    def get_other_party_name(self, obj):
        return _display_name(self._other(obj))

    def get_last_message(self, obj):
        message = obj.messages.order_by("-created_at").first()
        if message is None:
            return None
        return {
            "text": message.text,
            "created_at": message.created_at,
            "sender_id": message.sender_id,
        }

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(is_read=False).exclude(sender=request.user).count()


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = [
            "id",
            "channel",
            "recipient",
            "status",
            "attempts",
            "provider_reference",
            "last_error",
            "last_attempted_at",
            "sent_at",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    deliveries = NotificationDeliverySerializer(many=True, read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "kind",
            "priority",
            "action_url",
            "channels",
            "metadata",
            "is_read",
            "read_at",
            "expires_at",
            "created_at",
            "deliveries",
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        exclude = ["user"]
        read_only_fields = ["updated_at"]


from .models import DeviceRegistration, NotificationTemplate


class DeviceRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceRegistration
        fields = ["id", "platform", "token", "device_name", "active", "last_seen_at", "created_at"]
        read_only_fields = ["id", "last_seen_at", "created_at"]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = "__all__"
