import hashlib
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import PartnerAccessToken


class PartnerTokenPrincipal:
    def __init__(self, token):
        self.token = token
        self.application = token.application
        self.subject = token.subject
        self.is_authenticated = True
        self.is_anonymous = False
        self.role = "partner_application"
        self.email = f"{token.application.client_id}@partner.mydoctor"
        self.id = token.subject_id or 0

    @property
    def display_name(self):
        return self.application.name


class PartnerTokenAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if len(auth) != 2 or auth[0].lower() != self.keyword:
            return None
        raw = auth[1].decode("utf-8")
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        token = PartnerAccessToken.objects.select_related("application", "subject").filter(token_hash=token_hash, revoked_at__isnull=True, expires_at__gt=timezone.now(), application__active=True).first()
        if not token:
            raise AuthenticationFailed("Invalid or expired partner token.")
        request.partner_scopes = set(token.scopes or [])
        return PartnerTokenPrincipal(token), token
