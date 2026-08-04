from django.contrib import admin

from .models import (
    Conversation,
    Message,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationTemplate,
)

admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(Notification)
admin.site.register(NotificationDelivery)
admin.site.register(NotificationPreference)
admin.site.register(NotificationTemplate)
