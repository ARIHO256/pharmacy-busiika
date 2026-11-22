import asyncio
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Q

from .models import Conversation


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Authenticate in the first frame so JWTs never appear in URLs or access logs."""

    async def connect(self):
        self.user_id = None
        self.group = None
        self.window_start, self.frames = time.monotonic(), 0
        await self.accept()
        self.expiry_task = asyncio.create_task(self.expire(10))

    async def expire(self, seconds):
        await asyncio.sleep(seconds)
        await self.close(code=4401)

    @database_sync_to_async
    def authenticate(self, token):
        try:
            auth = JWTAuthentication()
            validated = auth.get_validated_token(token)
            user = auth.get_user(validated)
            conversation = Conversation.objects.filter(pk=self.scope["url_route"]["kwargs"]["pk"]).first()
            if not conversation or user.pk not in {conversation.patient_id, conversation.doctor_id}:
                return None
            if user.role == "doctor" and not user.is_verified:
                return None
            return user.pk, validated["exp"]
        except Exception:
            return None

    @database_sync_to_async
    def still_authorized(self):
        from accounts.models import User
        user = User.objects.filter(pk=self.user_id, is_active=True).first()
        if not user or user.role == "doctor" and not user.is_verified:
            return False
        return Conversation.objects.filter(pk=self.scope["url_route"]["kwargs"]["pk"]).filter(
            Q(patient_id=user.pk) | Q(doctor_id=user.pk)
        ).exists()

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if bytes_data is not None or text_data is None or len(text_data) > 8192:
            await self.close(code=4400)
            return
        try:
            await super().receive(text_data=text_data, **kwargs)
        except (ValueError, TypeError):
            await self.close(code=4400)

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            await self.close(code=4400)
            return
        if not self.user_id:
            if content.get("type") != "authenticate" or not isinstance(content.get("access_token"), str):
                await self.close(code=4401)
                return
            result = await self.authenticate(content["access_token"])
            if not result:
                await self.close(code=4403)
                return
            self.user_id, expiry = result
            self.expiry_task.cancel()
            self.expiry_task = asyncio.create_task(self.expire(max(0, expiry - time.time())))
            self.group = f"conversation.{self.scope['url_route']['kwargs']['pk']}"
            await self.channel_layer.group_add(self.group, self.channel_name)
            await self.send_json({"type": "ready"})
            return
        if time.monotonic() - self.window_start > 60:
            self.window_start, self.frames = time.monotonic(), 0
        self.frames += 1
        if self.frames > 120 or not await self.still_authorized():
            await self.close(code=4403)
            return
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def chat_changed(self, event):
        if not await self.still_authorized():
            await self.close(code=4403)
            return
        await self.send_json({"type": event["kind"], "message_id": event.get("message_id")})

    async def disconnect(self, code):
        if getattr(self, "expiry_task", None):
            self.expiry_task.cancel()
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)
