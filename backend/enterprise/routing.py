from django.urls import path
from .consumers import ConversationConsumer, NotificationConsumer, TelemedicineConsumer

websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),
    path("ws/conversations/<int:conversation_id>/", ConversationConsumer.as_asgi()),
    path("ws/telemedicine/<uuid:session_id>/", TelemedicineConsumer.as_asgi()),
]
