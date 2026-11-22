"""Chat persistence is authoritative; WebSocket messages are refresh hints."""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction


def broadcast(conversation_id, kind, message_id=None):
    def publish():
        import logging
        try:
            async_to_sync(get_channel_layer().group_send)(f"conversation.{conversation_id}", {
                "type": "chat.changed", "kind": kind, "message_id": message_id,
            })
        except Exception:
            # A broker outage cannot roll back a persisted message; clients also poll.
            logging.getLogger(__name__).warning("Chat refresh notification could not be delivered")
    transaction.on_commit(publish)
