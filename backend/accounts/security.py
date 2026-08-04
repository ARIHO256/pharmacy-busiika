import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OneTimeToken, SecurityEvent, User


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def record_security_event(request, event_type, user=None, **detail):
    SecurityEvent.objects.create(
        user=user,
        event_type=event_type,
        ip_address=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        request_id=getattr(request, "request_id", ""),
        detail=detail,
    )


def hash_token(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(user, purpose, request=None, minutes=30, numeric=False, metadata=None):
    OneTimeToken.objects.filter(
        user=user,
        purpose=purpose,
        consumed_at__isnull=True,
    ).update(consumed_at=timezone.now())
    raw = f"{secrets.randbelow(1_000_000):06d}" if numeric else secrets.token_urlsafe(32)
    row = OneTimeToken.objects.create(
        user=user,
        purpose=purpose,
        token_hash=hash_token(raw),
        expires_at=timezone.now() + timedelta(minutes=minutes),
        request_ip=client_ip(request) if request else None,
        metadata=metadata or {},
    )
    return row, raw


def consume_token(public_id, raw, purpose, max_attempts=6):
    token = OneTimeToken.objects.select_related("user").filter(
        public_id=public_id,
        purpose=purpose,
        consumed_at__isnull=True,
    ).first()
    if not token or token.expires_at <= timezone.now():
        raise ValidationError({"detail": "This code or link is invalid or has expired."})
    token.attempts += 1
    token.save(update_fields=["attempts"])
    if token.attempts > max_attempts:
        token.consumed_at = timezone.now()
        token.save(update_fields=["consumed_at"])
        raise ValidationError({"detail": "Too many invalid attempts. Request a new code."})
    if not secrets.compare_digest(token.token_hash, hash_token(str(raw))):
        raise ValidationError({"detail": "The supplied code or token is invalid."})
    token.consumed_at = timezone.now()
    token.save(update_fields=["consumed_at"])
    return token.user


def issue_jwt(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def send_security_email(user, subject, body):
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def account_login(request, email, password):
    normalized = User.objects.normalize_email(email or "")
    user = User.objects.filter(email__iexact=normalized).first()
    now = timezone.now()
    if user and user.locked_until and user.locked_until > now:
        record_security_event(request, SecurityEvent.Type.LOGIN_FAILED, user, reason="locked")
        raise AuthenticationFailed("Account temporarily locked. Try again later or reset your password.")

    authenticated = authenticate(request=request, email=normalized, password=password)
    if not authenticated:
        if user:
            user.failed_login_attempts += 1
            fields = ["failed_login_attempts"]
            threshold = int(getattr(settings, "LOGIN_FAILURE_LOCK_THRESHOLD", 5))
            if user.failed_login_attempts >= threshold:
                user.locked_until = now + timedelta(minutes=int(getattr(settings, "LOGIN_LOCK_MINUTES", 15)))
                fields.append("locked_until")
                record_security_event(request, SecurityEvent.Type.ACCOUNT_LOCKED, user, threshold=threshold)
            user.save(update_fields=fields)
        record_security_event(request, SecurityEvent.Type.LOGIN_FAILED, user, email=normalized)
        raise AuthenticationFailed("Invalid email or password.")

    if not authenticated.is_active:
        raise AuthenticationFailed("This account is inactive.")

    authenticated.failed_login_attempts = 0
    authenticated.locked_until = None
    authenticated.save(update_fields=["failed_login_attempts", "locked_until", "last_login"])
    record_security_event(request, SecurityEvent.Type.LOGIN_SUCCESS, authenticated)
    return authenticated
