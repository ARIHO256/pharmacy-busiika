"""Production notification provider adapters using the Python standard library.

No secrets are stored in the database. Configure providers through environment
variables and rotate credentials through the deployment secret manager.
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(RuntimeError):
    pass


def _request(url, *, data=None, headers=None, method="POST", timeout=20):
    payload = data
    if isinstance(data, (dict, list)):
        payload = json.dumps(data).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"Provider HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Provider connection failed: {exc.reason}") from exc


class AfricaTalkingSmsProvider:
    def send(self, recipient, body):
        username = os.getenv("AFRICASTALKING_USERNAME", "")
        api_key = os.getenv("AFRICASTALKING_API_KEY", "")
        sender = os.getenv("AFRICASTALKING_SENDER_ID", "")
        if not username or not api_key:
            raise ProviderError("Africa's Talking credentials are not configured.")
        form = {"username": username, "to": recipient, "message": body}
        if sender:
            form["from"] = sender
        status, data = _request(
            os.getenv("AFRICASTALKING_SMS_URL", "https://api.africastalking.com/version1/messaging"),
            data=urllib.parse.urlencode(form).encode("utf-8"),
            headers={"apiKey": api_key, "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        )
        recipients = data.get("SMSMessageData", {}).get("Recipients", [])
        if not recipients:
            raise ProviderError(data.get("SMSMessageData", {}).get("Message", "SMS was not accepted."))
        row = recipients[0]
        return str(row.get("messageId") or row.get("messageParts") or "accepted")


class TwilioSmsProvider:
    def send(self, recipient, body):
        sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        token = os.getenv("TWILIO_AUTH_TOKEN", "")
        sender = os.getenv("TWILIO_FROM_NUMBER", "")
        if not sid or not token or not sender:
            raise ProviderError("Twilio SMS credentials are not configured.")
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        form = urllib.parse.urlencode({"To": recipient, "From": sender, "Body": body}).encode()
        _, data = _request(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data=form,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        )
        return str(data.get("sid") or "accepted")


class GenericWebhookProvider:
    def __init__(self, url_env, token_env):
        self.url = os.getenv(url_env, "")
        self.token = os.getenv(token_env, "")

    def send(self, recipient, title, body, metadata=None):
        if not self.url:
            raise ProviderError("Notification webhook URL is not configured.")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        _, data = _request(self.url, data={"recipient": recipient, "title": title, "body": body, "metadata": metadata or {}}, headers=headers)
        return str(data.get("id") or data.get("reference") or "accepted")


class FcmPushProvider:
    """Firebase Cloud Messaging HTTP v1 adapter.

    Configure either ``FCM_SERVICE_ACCOUNT_FILE`` or
    ``FCM_SERVICE_ACCOUNT_JSON`` and ``FCM_PROJECT_ID``. The legacy server-key
    endpoint is intentionally not used.
    """

    def _credentials(self):
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request as GoogleAuthRequest
        except ImportError as exc:
            raise ProviderError("google-auth is required for FCM HTTP v1 delivery.") from exc

        scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
        raw_json = os.getenv("FCM_SERVICE_ACCOUNT_JSON", "").strip()
        filename = os.getenv("FCM_SERVICE_ACCOUNT_FILE", "").strip()
        if raw_json:
            try:
                info = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                raise ProviderError("FCM_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
            credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        elif filename:
            credentials = service_account.Credentials.from_service_account_file(filename, scopes=scopes)
        else:
            raise ProviderError("FCM service-account credentials are not configured.")
        credentials.refresh(GoogleAuthRequest())
        return credentials

    def send(self, token, title, body, metadata=None):
        project_id = os.getenv("FCM_PROJECT_ID", "").strip()
        if not project_id:
            raise ProviderError("FCM_PROJECT_ID is not configured.")
        credentials = self._credentials()
        data_payload = {str(key): str(value) for key, value in (metadata or {}).items()}
        _, data = _request(
            os.getenv(
                "FCM_ENDPOINT",
                f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            ),
            data={
                "message": {
                    "token": token,
                    "notification": {"title": title, "body": body},
                    "data": data_payload,
                }
            },
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        message_name = data.get("name")
        if not message_name:
            raise ProviderError(f"FCM did not return a message name: {data}")
        return str(message_name)


class MetaWhatsAppProvider:
    def send(self, recipient, body):
        token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        if not token or not phone_id:
            raise ProviderError("WhatsApp Cloud API credentials are not configured.")
        _, data = _request(
            f"https://graph.facebook.com/{os.getenv('WHATSAPP_GRAPH_VERSION', 'v21.0')}/{phone_id}/messages",
            data={"messaging_product": "whatsapp", "to": recipient.lstrip("+"), "type": "text", "text": {"body": body}},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        messages = data.get("messages", [])
        return str(messages[0].get("id") if messages else "accepted")


class ConfiguredWebhookProvider:
    def __init__(self, provider):
        self.provider = provider

    def send(self, recipient, title, body, metadata=None):
        config = self.provider.configuration or {}
        url = config.get("url") or config.get("base_url")
        if not url:
            raise ProviderError(f"Webhook URL is missing for {self.provider.name}.")
        token = os.getenv(self.provider.credentials_reference, "") if self.provider.credentials_reference else ""
        headers = {"Content-Type": "application/json", **(config.get("headers") or {})}
        if token:
            headers[config.get("auth_header", "Authorization")] = f"{config.get('auth_scheme', 'Bearer')} {token}".strip()
        _, data = _request(url, data={
            "recipient": recipient, "title": title, "body": body, "channel": self.provider.channel,
            "sender": config.get("sender", "MyDoctor"), "metadata": metadata or {},
        }, headers=headers, timeout=int(config.get("timeout_seconds", 20)))
        return str(data.get("id") or data.get("reference") or data.get("message_id") or "accepted")


def _environment_provider(channel):
    if channel == "sms":
        name = os.getenv("SMS_PROVIDER", "").lower()
        if name == "africastalking": return AfricaTalkingSmsProvider()
        if name == "twilio": return TwilioSmsProvider()
        if name == "webhook": return GenericWebhookProvider("SMS_WEBHOOK_URL", "SMS_WEBHOOK_TOKEN")
        raise ProviderError("SMS_PROVIDER must be africastalking, twilio or webhook.")
    if channel == "push":
        return GenericWebhookProvider("PUSH_WEBHOOK_URL", "PUSH_WEBHOOK_TOKEN") if os.getenv("PUSH_PROVIDER", "fcm").lower() == "webhook" else FcmPushProvider()
    if channel == "whatsapp":
        return GenericWebhookProvider("WHATSAPP_WEBHOOK_URL", "WHATSAPP_WEBHOOK_TOKEN") if os.getenv("WHATSAPP_PROVIDER", "meta").lower() == "webhook" else MetaWhatsAppProvider()
    raise ProviderError(f"Unsupported channel: {channel}")


def _configured_providers(channel):
    try:
        from enterprise.models import NotificationProvider
        return list(NotificationProvider.objects.filter(channel=channel, active=True).order_by("priority", "id"))
    except Exception:
        return []


def _provider_adapter(row):
    provider_type = row.provider_type.lower()
    if provider_type in {"webhook", "generic_webhook"}: return ConfiguredWebhookProvider(row)
    if provider_type in {"africastalking", "africas_talking"}: return AfricaTalkingSmsProvider()
    if provider_type == "twilio": return TwilioSmsProvider()
    if provider_type in {"fcm", "firebase"}: return FcmPushProvider()
    if provider_type in {"meta", "whatsapp_cloud"}: return MetaWhatsAppProvider()
    raise ProviderError(f"Unsupported configured provider type: {row.provider_type}")


def _deliver(channel, recipient, title, body, metadata=None):
    errors = []
    providers = _configured_providers(channel)
    for row in providers:
        try:
            adapter = _provider_adapter(row)
            if isinstance(adapter, (AfricaTalkingSmsProvider, TwilioSmsProvider, MetaWhatsAppProvider)):
                reference = adapter.send(recipient, body)
            else:
                reference = adapter.send(recipient, title, body, metadata)
            try:
                from django.utils import timezone
                row.health_status = "healthy"
                row.last_health_check_at = timezone.now()
                row.save(update_fields=["health_status", "last_health_check_at"])
            except Exception:
                pass
            return f"{row.name}:{reference}"
        except Exception as exc:
            errors.append(f"{row.name}: {exc}")
            try:
                from django.utils import timezone
                row.health_status = "degraded"
                row.last_health_check_at = timezone.now()
                row.save(update_fields=["health_status", "last_health_check_at"])
            except Exception:
                pass
    try:
        adapter = _environment_provider(channel)
        if isinstance(adapter, (AfricaTalkingSmsProvider, TwilioSmsProvider, MetaWhatsAppProvider)):
            return adapter.send(recipient, body)
        return adapter.send(recipient, title, body, metadata)
    except Exception as exc:
        errors.append(f"environment fallback: {exc}")
        raise ProviderError("; ".join(errors)) from exc


def sms_provider():
    return _environment_provider("sms")


def send_sms(recipient, title, body, metadata=None):
    return _deliver("sms", recipient, title, body, metadata)


def send_push(recipient, title, body, metadata=None):
    return _deliver("push", recipient, title, body, metadata)


def send_whatsapp(recipient, title, body, metadata=None):
    return _deliver("whatsapp", recipient, title, body, metadata)
