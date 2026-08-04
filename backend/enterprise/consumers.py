from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone


class AuthenticatedConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if not self.scope.get("user") or not self.scope["user"].is_authenticated:
            await self.close(code=4401)
            return
        await self.accept()


class NotificationConsumer(AuthenticatedConsumer):
    async def connect(self):
        await super().connect()
        if self.scope.get("user") and self.scope["user"].is_authenticated:
            self.group_name = f"user-notifications-{self.scope['user'].id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.set_presence("online", 1)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.set_presence("offline", -1)

    async def notification_event(self, event):
        await self.send_json({"type": "notification", "notification": event["notification"]})

    async def presence_event(self, event):
        await self.send_json({"type": "presence", "presence": event["presence"]})

    @database_sync_to_async
    def set_presence(self, status, delta):
        from .models import PresenceState
        state, _ = PresenceState.objects.get_or_create(user=self.scope["user"])
        state.connection_count = max(0, state.connection_count + delta)
        state.status = "online" if state.connection_count else status
        state.last_seen_at = timezone.now()
        state.save(update_fields=["connection_count", "status", "last_seen_at"])


class ConversationConsumer(AuthenticatedConsumer):
    async def connect(self):
        await super().connect()
        if not self.scope.get("user") or not self.scope["user"].is_authenticated:
            return
        self.conversation_id = int(self.scope["url_route"]["kwargs"]["conversation_id"])
        if not await self.can_join():
            await self.close(code=4403)
            return
        self.group_name = f"conversation-{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        if event_type == "message.send":
            message = await self.create_message(content.get("text", ""))
            await self.channel_layer.group_send(self.group_name, {"type": "chat.message", "message": message})
        elif event_type == "message.read":
            receipt = await self.mark_read(content.get("message_id"))
            await self.channel_layer.group_send(self.group_name, {"type": "chat.receipt", "receipt": receipt})
        elif event_type == "typing":
            await self.channel_layer.group_send(self.group_name, {"type": "chat.typing", "user_id": self.scope["user"].id, "typing": bool(content.get("typing"))})

    async def chat_message(self, event):
        await self.send_json({"type": "message", "message": event["message"]})

    async def chat_receipt(self, event):
        await self.send_json({"type": "receipt", "receipt": event["receipt"]})

    async def chat_typing(self, event):
        if event["user_id"] != self.scope["user"].id:
            await self.send_json({"type": "typing", "user_id": event["user_id"], "typing": event["typing"]})

    @database_sync_to_async
    def can_join(self):
        from communication.models import Conversation
        from enterprise.access import is_platform_super_admin
        user = self.scope["user"]
        return Conversation.objects.filter(id=self.conversation_id).filter(patient=user).exists() or Conversation.objects.filter(id=self.conversation_id).filter(doctor=user).exists() or is_platform_super_admin(user)

    @database_sync_to_async
    def create_message(self, text):
        from communication.models import Conversation, Message
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(conversation=conversation, sender=self.scope["user"], text=text[:10000])
        return {"id": message.id, "conversation": conversation.id, "sender": message.sender_id, "sender_name": message.sender.display_name, "text": message.text, "created_at": message.created_at.isoformat()}

    @database_sync_to_async
    def mark_read(self, message_id):
        from communication.models import Message
        from .models import MessageReceipt
        message = Message.objects.get(id=message_id, conversation_id=self.conversation_id)
        receipt, _ = MessageReceipt.objects.get_or_create(message=message, user=self.scope["user"])
        receipt.delivered_at = receipt.delivered_at or timezone.now()
        receipt.read_at = timezone.now()
        receipt.save(update_fields=["delivered_at", "read_at"])
        message.is_read = True
        message.save(update_fields=["is_read"])
        return {"message_id": message.id, "user_id": self.scope["user"].id, "delivered_at": receipt.delivered_at.isoformat(), "read_at": receipt.read_at.isoformat()}


class TelemedicineConsumer(AuthenticatedConsumer):
    async def connect(self):
        await super().connect()
        if not self.scope.get("user") or not self.scope["user"].is_authenticated:
            return
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        if not await self.can_join():
            await self.close(code=4403)
            return
        self.group_name = f"telemedicine-{self.session_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_send(self.group_name, {"type": "session.presence", "user_id": self.scope["user"].id, "status": "connected"})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_send(self.group_name, {"type": "session.presence", "user_id": self.scope["user"].id, "status": "disconnected"})
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        if event_type in {"raise_hand", "admit", "mute_request", "quality", "screen_share", "end_session"}:
            await self.channel_layer.group_send(self.group_name, {"type": "session.control", "event": event_type, "user_id": self.scope["user"].id, "payload": content.get("payload", {})})

    async def session_control(self, event):
        await self.send_json({"type": "session.control", **event})

    async def session_presence(self, event):
        await self.send_json({"type": "session.presence", "user_id": event["user_id"], "status": event["status"]})

    @database_sync_to_async
    def can_join(self):
        from .models import TelemedicineSession
        from .access import active_role, is_platform_super_admin
        user = self.scope["user"]
        session = TelemedicineSession.objects.filter(public_id=self.session_id).first()
        if not session:
            return False
        return bool(
            session.participants.filter(user=user).exists()
            or is_platform_super_admin(user)
            or active_role(user) in {"receptionist", "operations_admin"}
        )
