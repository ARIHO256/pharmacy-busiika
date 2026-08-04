from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "user", "action", "meta", "created_at"]

    def get_user(self, obj):
        return obj.user.email if obj.user else None
