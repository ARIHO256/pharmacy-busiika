"""Hosted payment gateway adapters.

The adapters keep secret keys server-side, use idempotent invoice references and
always expose a verification method so webhook payloads are never trusted alone.
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class GatewayError(RuntimeError):
    pass


def _json_request(url, *, method="GET", payload=None, headers=None, timeout=30):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise GatewayError(f"Gateway HTTP {exc.code}: {raw[:800]}") from exc
    except urllib.error.URLError as exc:
        raise GatewayError(f"Gateway connection failed: {exc.reason}") from exc


class MockGateway:
    name = "mock"

    def initiate(self, invoice, phone=None):
        return {"ref": f"MOCK-{invoice.number}", "checkout_url": f"/api/payments/webhook/mock/{invoice.number}/"}

    def verify(self, reference=None, transaction_id=None):
        return {"successful": True, "reference": reference, "amount": None, "currency": None, "provider_id": transaction_id or reference}

    def refund(self, payment, amount, reason=""):
        return {"reference": f"MOCK-REFUND-{payment.number}", "status": "processed"}


class FlutterwaveGateway:
    name = "flutterwave"

    def __init__(self):
        self.secret_key = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
        self.base_url = os.getenv("FLUTTERWAVE_V3_BASE_URL", "https://api.flutterwave.com/v3").rstrip("/")
        if not self.secret_key:
            raise GatewayError("FLUTTERWAVE_SECRET_KEY is not configured.")

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json"}

    def initiate(self, invoice, phone=None):
        redirect_url = os.getenv("PAYMENT_REDIRECT_URL", f"{settings.FRONTEND_URL}/patient/invoices")
        payload = {
            "tx_ref": invoice.number,
            "amount": str(invoice.balance or invoice.amount),
            "currency": invoice.currency,
            "redirect_url": redirect_url,
            "payment_options": os.getenv("FLUTTERWAVE_PAYMENT_OPTIONS", "card,mobilemoneyuganda"),
            "customer": {
                "email": invoice.patient.email,
                "name": invoice.patient.display_name,
                "phonenumber": phone or invoice.patient.phone,
            },
            "customizations": {"title": "HealthPilot", "description": f"Payment for invoice {invoice.number}"},
            "meta": {"invoice_id": invoice.id, "invoice_number": invoice.number},
        }
        data = _json_request(f"{self.base_url}/payments", method="POST", payload=payload, headers=self.headers)
        link = data.get("data", {}).get("link")
        if data.get("status") != "success" or not link:
            raise GatewayError(data.get("message", "Flutterwave did not return a checkout link."))
        return {"ref": invoice.number, "checkout_url": link}

    def verify(self, reference=None, transaction_id=None):
        if not transaction_id:
            raise GatewayError("Flutterwave transaction ID is required for verification.")
        data = _json_request(f"{self.base_url}/transactions/{transaction_id}/verify", headers=self.headers)
        row = data.get("data", {})
        return {
            "successful": row.get("status") == "successful",
            "reference": row.get("tx_ref") or row.get("reference"),
            "amount": int(float(row.get("amount", 0))),
            "currency": row.get("currency"),
            "provider_id": str(row.get("id") or transaction_id),
            "raw": row,
        }

    def refund(self, payment, amount, reason=""):
        transaction_id = payment.reference
        data = _json_request(
            f"{self.base_url}/transactions/{transaction_id}/refund",
            method="POST",
            payload={"amount": amount, "comments": reason},
            headers=self.headers,
        )
        row = data.get("data", {})
        return {"reference": str(row.get("id") or transaction_id), "status": row.get("status", data.get("status", "pending"))}


class PaystackGateway:
    name = "paystack"

    def __init__(self):
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
        self.base_url = os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co").rstrip("/")
        self.multiplier = int(os.getenv("PAYSTACK_SUBUNIT_MULTIPLIER", "1"))
        if not self.secret_key:
            raise GatewayError("PAYSTACK_SECRET_KEY is not configured.")

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json"}

    def initiate(self, invoice, phone=None):
        payload = {
            "email": invoice.patient.email,
            "amount": int(invoice.balance or invoice.amount) * self.multiplier,
            "currency": invoice.currency,
            "reference": invoice.number,
            "callback_url": os.getenv("PAYMENT_REDIRECT_URL", f"{settings.FRONTEND_URL}/patient/invoices"),
            "metadata": {"invoice_id": invoice.id, "invoice_number": invoice.number, "phone": phone or invoice.patient.phone},
        }
        data = _json_request(f"{self.base_url}/transaction/initialize", method="POST", payload=payload, headers=self.headers)
        row = data.get("data", {})
        if not data.get("status") or not row.get("authorization_url"):
            raise GatewayError(data.get("message", "Paystack did not return a checkout link."))
        return {"ref": row.get("reference") or invoice.number, "checkout_url": row["authorization_url"], "access_code": row.get("access_code")}

    def verify(self, reference=None, transaction_id=None):
        if not reference:
            raise GatewayError("Paystack reference is required for verification.")
        encoded = urllib.parse.quote(reference, safe="")
        data = _json_request(f"{self.base_url}/transaction/verify/{encoded}", headers=self.headers)
        row = data.get("data", {})
        return {
            "successful": bool(data.get("status")) and row.get("status") == "success",
            "reference": row.get("reference"),
            "amount": int(row.get("amount", 0)) // self.multiplier,
            "currency": row.get("currency"),
            "provider_id": str(row.get("id") or reference),
            "raw": row,
        }

    def refund(self, payment, amount, reason=""):
        data = _json_request(
            f"{self.base_url}/refund",
            method="POST",
            payload={"transaction": payment.reference, "amount": int(amount) * self.multiplier, "customer_note": reason, "merchant_note": reason},
            headers=self.headers,
        )
        row = data.get("data", {})
        return {"reference": str(row.get("id") or row.get("transaction", {}).get("reference") or payment.reference), "status": row.get("status", "pending")}


class MtnMomoGateway:
    """MTN MoMo Collection adapter for Uganda and other configured markets."""

    name = "mtn_momo"

    def __init__(self):
        self.base_url = os.getenv("MTN_MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com").rstrip("/")
        self.subscription_key = os.getenv("MTN_MOMO_SUBSCRIPTION_KEY", "")
        self.api_user = os.getenv("MTN_MOMO_API_USER", "")
        self.api_key = os.getenv("MTN_MOMO_API_KEY", "")
        self.environment = os.getenv("MTN_MOMO_TARGET_ENVIRONMENT", "sandbox")
        self.currency = os.getenv("MTN_MOMO_CURRENCY", "EUR" if self.environment == "sandbox" else "UGX")
        if not all((self.subscription_key, self.api_user, self.api_key)):
            raise GatewayError("MTN MoMo collection credentials are not configured.")

    def _token(self):
        basic = base64.b64encode(f"{self.api_user}:{self.api_key}".encode()).decode()
        request = urllib.request.Request(
            f"{self.base_url}/collection/token/",
            method="POST",
            headers={"Authorization": f"Basic {basic}", "Ocp-Apim-Subscription-Key": self.subscription_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())["access_token"]
        except Exception as exc:
            raise GatewayError(f"MTN MoMo token request failed: {exc}") from exc

    def _headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": self.environment,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json",
        }

    def initiate(self, invoice, phone=None):
        import uuid
        phone = (phone or invoice.patient.phone or "").replace("+", "")
        if not phone:
            raise GatewayError("A mobile-money phone number is required.")
        reference = str(uuid.uuid4())
        payload = {
            "amount": str(invoice.balance or invoice.amount),
            "currency": invoice.currency if self.environment != "sandbox" else self.currency,
            "externalId": invoice.number,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": f"HealthPilot invoice {invoice.number}",
            "payeeNote": f"Healthcare payment for {invoice.number}",
        }
        headers = {**self._headers(self._token()), "X-Reference-Id": reference}
        _json_request(f"{self.base_url}/collection/v1_0/requesttopay", method="POST", payload=payload, headers=headers)
        return {"ref": reference, "provider_reference": reference, "status": "pending", "checkout_url": "", "instructions": "Approve the MTN MoMo prompt on the payer phone."}

    def verify(self, reference=None, transaction_id=None):
        reference = transaction_id or reference
        if not reference:
            raise GatewayError("MTN MoMo reference is required.")
        row = _json_request(f"{self.base_url}/collection/v1_0/requesttopay/{urllib.parse.quote(reference)}", headers=self._headers(self._token()))
        status = str(row.get("status", "")).upper()
        return {
            "successful": status == "SUCCESSFUL",
            "pending": status == "PENDING",
            "reference": row.get("externalId"),
            "amount": int(float(row.get("amount", 0))) if row.get("amount") is not None else None,
            "currency": row.get("currency"),
            "provider_id": reference,
            "raw": row,
        }

    def refund(self, payment, amount, reason=""):
        endpoint = os.getenv("MTN_MOMO_REFUND_WEBHOOK_URL", "")
        if not endpoint:
            raise GatewayError("MTN MoMo refund/disbursement endpoint is not configured.")
        data = _json_request(endpoint, method="POST", payload={"payment_reference": payment.reference, "amount": int(amount), "reason": reason}, headers={"Authorization": f"Bearer {os.getenv('MTN_MOMO_REFUND_WEBHOOK_TOKEN', '')}", "Content-Type": "application/json"})
        return {"reference": str(data.get("reference") or data.get("id") or payment.reference), "status": data.get("status", "pending")}


class AirtelMoneyGateway:
    """Airtel Money Africa collection adapter with configurable country/currency."""

    name = "airtel_money"

    def __init__(self):
        self.base_url = os.getenv("AIRTEL_MONEY_BASE_URL", "https://openapiuat.airtel.africa").rstrip("/")
        self.client_id = os.getenv("AIRTEL_MONEY_CLIENT_ID", "")
        self.client_secret = os.getenv("AIRTEL_MONEY_CLIENT_SECRET", "")
        self.country = os.getenv("AIRTEL_MONEY_COUNTRY", "UG")
        self.currency = os.getenv("AIRTEL_MONEY_CURRENCY", "UGX")
        if not self.client_id or not self.client_secret:
            raise GatewayError("Airtel Money credentials are not configured.")

    def _token(self):
        row = _json_request(f"{self.base_url}/auth/oauth2/token", method="POST", payload={"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"}, headers={"Content-Type": "application/json"})
        token = row.get("access_token")
        if not token:
            raise GatewayError(f"Airtel Money did not return an access token: {row}")
        return token

    def _headers(self):
        return {"Authorization": f"Bearer {self._token()}", "X-Country": self.country, "X-Currency": self.currency, "Content-Type": "application/json"}

    def initiate(self, invoice, phone=None):
        import uuid
        phone = (phone or invoice.patient.phone or "").replace("+", "")
        if not phone:
            raise GatewayError("A mobile-money phone number is required.")
        reference = str(uuid.uuid4())
        payload = {
            "reference": invoice.number,
            "subscriber": {"country": self.country, "currency": self.currency, "msisdn": phone},
            "transaction": {"amount": int(invoice.balance or invoice.amount), "country": self.country, "currency": invoice.currency, "id": reference},
        }
        row = _json_request(f"{self.base_url}/merchant/v1/payments/", method="POST", payload=payload, headers=self._headers())
        return {"ref": reference, "provider_reference": reference, "status": str(row.get("status", {}).get("code", "pending")), "checkout_url": "", "instructions": "Approve the Airtel Money prompt on the payer phone.", "raw": row}

    def verify(self, reference=None, transaction_id=None):
        reference = transaction_id or reference
        if not reference:
            raise GatewayError("Airtel Money transaction reference is required.")
        row = _json_request(f"{self.base_url}/standard/v1/payments/{urllib.parse.quote(reference)}", headers=self._headers())
        transaction = row.get("data", {}).get("transaction", {})
        status = str(transaction.get("status", "")).upper()
        return {
            "successful": status in {"TS", "SUCCESS", "SUCCESSFUL"},
            "pending": status in {"TIP", "PENDING", "PROCESSING"},
            "reference": transaction.get("reference") or row.get("reference"),
            "amount": int(float(transaction.get("amount", 0))) if transaction.get("amount") is not None else None,
            "currency": transaction.get("currency") or self.currency,
            "provider_id": reference,
            "raw": row,
        }

    def refund(self, payment, amount, reason=""):
        import uuid
        reference = str(uuid.uuid4())
        payload = {"transaction": {"airtel_money_id": payment.reference, "id": reference}, "amount": int(amount), "reason": reason}
        row = _json_request(f"{self.base_url}/standard/v1/payments/refund", method="POST", payload=payload, headers=self._headers())
        return {"reference": reference, "status": row.get("status", {}).get("message", "pending"), "raw": row}


def get_gateway(name=None):
    if name is None:
        name = "mock" if getattr(settings, "MOCK_PAYMENTS", False) else os.getenv("PAYMENT_GATEWAY", "flutterwave")
    gateways = {"mock": MockGateway, "flutterwave": FlutterwaveGateway, "paystack": PaystackGateway, "mtn_momo": MtnMomoGateway, "airtel_money": AirtelMoneyGateway}
    try:
        return gateways[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown gateway: {name}") from exc
