from django.urls import path

from .views import (
    ConversationsView,
    MessagesView,
    NotificationPreferencesView,
    NotificationReadAllView,
    NotificationReadView,
    NotificationsView,
    VideoRoomView, DeviceRegistrationView, NotificationBroadcastView, NotificationDeliveryCallbackView, NotificationTemplateAdminView,
)

urlpatterns = [
    path("notifications/devices/", DeviceRegistrationView.as_view(), name="notification-devices"),
    path("notifications/devices/<int:pk>/", DeviceRegistrationView.as_view(), name="notification-device-detail"),
    path("admin/notification-templates/", NotificationTemplateAdminView.as_view(), name="notification-templates"),
    path("admin/notification-templates/<int:pk>/", NotificationTemplateAdminView.as_view(), name="notification-template-detail"),
    path("admin/notification-broadcast/", NotificationBroadcastView.as_view(), name="notification-broadcast"),
    path("notifications/delivery-callback/<str:channel>/", NotificationDeliveryCallbackView.as_view(), name="notification-delivery-callback"),
    path("conversations/", ConversationsView.as_view(), name="conversations"),
    path("conversations/<int:pk>/messages/", MessagesView.as_view(), name="conversation-messages"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
    path("notifications/read-all/", NotificationReadAllView.as_view(), name="notification-read-all"),
    path("notifications/preferences/", NotificationPreferencesView.as_view(), name="notification-preferences"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("appointments/<int:pk>/video-room/", VideoRoomView.as_view(), name="video-room"),
]
