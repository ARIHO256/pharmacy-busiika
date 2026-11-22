from django.urls import path

from .views import (
    ConversationsView,
    MessagesView,
    MessageSyncView,
    NotificationPreferencesView,
    NotificationReadAllView,
    NotificationReadView,
    NotificationsView,
    VideoRoomView,
)

urlpatterns = [
    path("conversations/", ConversationsView.as_view(), name="conversations"),
    path("conversations/<int:pk>/messages/", MessagesView.as_view(), name="conversation-messages"),
    path("conversations/<int:pk>/sync/", MessageSyncView.as_view(), name="conversation-sync"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
    path("notifications/read-all/", NotificationReadAllView.as_view(), name="notification-read-all"),
    path("notifications/preferences/", NotificationPreferencesView.as_view(), name="notification-preferences"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("appointments/<int:pk>/video-room/", VideoRoomView.as_view(), name="video-room"),
]
