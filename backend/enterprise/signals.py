from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from communication.models import Notification


@receiver(post_save, sender=Notification)
def publish_notification(sender, instance, created, **kwargs):
    if not created:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"user-notifications-{instance.user_id}",
        {
            "type": "notification.event",
            "notification": {
                "id": instance.id,
                "title": instance.title,
                "body": instance.body,
                "kind": instance.kind,
                "priority": instance.priority,
                "action_url": instance.action_url,
                "created_at": instance.created_at.isoformat(),
            },
        },
    )

from django.contrib.auth import get_user_model
from workforce.models import StaffMembership
from registry.models import PractitionerRole


@receiver(post_save, sender=get_user_model())
def ensure_default_role_context(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .models import ActiveRoleContext, RoleContext
        context, _ = RoleContext.objects.get_or_create(
            user=instance,
            organization=None,
            location=None,
            department=None,
            role_code=instance.role,
            defaults={"title": instance.get_role_display(), "is_primary": True, "active": True},
        )
        ActiveRoleContext.objects.get_or_create(user=instance, defaults={"context": context})
    except Exception:
        # During initial migration/syncdb the enterprise tables may not exist yet.
        return


@receiver(post_save, sender=StaffMembership)
def synchronize_staff_context(sender, instance, **kwargs):
    try:
        from .models import RoleContext
        RoleContext.objects.update_or_create(
            user=instance.user,
            organization=instance.organization,
            location=instance.department.location if instance.department_id else None,
            department=instance.department,
            role_code=instance.role,
            defaults={
                "title": instance.job_title,
                "is_primary": instance.is_primary,
                "active": instance.status == StaffMembership.Status.ACTIVE,
                "starts_on": instance.starts_on,
                "ends_on": instance.ends_on,
                "created_by": instance.created_by,
            },
        )
    except Exception:
        return


@receiver(post_save, sender=PractitionerRole)
def synchronize_practitioner_context(sender, instance, **kwargs):
    try:
        from .models import RoleContext
        RoleContext.objects.update_or_create(
            user=instance.practitioner,
            organization=instance.organization,
            location=instance.location,
            department=None,
            role_code=instance.practitioner.role,
            defaults={
                "title": instance.role_name,
                "active": instance.active,
                "starts_on": instance.start_date,
                "ends_on": instance.end_date,
            },
        )
    except Exception:
        return
