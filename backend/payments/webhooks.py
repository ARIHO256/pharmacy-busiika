import base64
import hashlib
import hmac
import json
import os

from django.db import transaction
from django.utils import timezone

from .gateways import GatewayError, get_gateway
from .models import Invoice, PaymentTransaction, PaymentWebhookEvent
from .services import confirm_invoice_payment


class InvalidWebhook(RuntimeError):
    pass


def verify_signature(gateway, raw_body, headers):
    if gateway == "paystack":
        secret = os.getenv("PAYSTACK_SECRET_KEY", "")
        supplied = headers.get("x-paystack-signature", "")
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest() if secret else ""
    elif gateway == "flutterwave":
        secret = os.getenv("FLUTTERWAVE_WEBHOOK_SECRET_HASH", "")
        supplied = headers.get("flutterwave-signature", "")
        expected = base64.b64encode(hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()).decode() if secret else ""
    elif gateway in {"mtn_momo", "airtel_money"}:
        secret = os.getenv(f"{gateway.upper()}_WEBHOOK_SECRET", "")
        supplied = headers.get("x-healthpilot-signature", "") or headers.get("x-signature", "")
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest() if secret else ""
    else:
        raise InvalidWebhook("Unsupported gateway.")
    return bool(secret and supplied and hmac.compare_digest(expected, supplied))


def parse_event(gateway, payload):
    data = payload.get("data") or {}
    if gateway == "paystack":
        return {
            "event_id": str(data.get("id") or payload.get("id") or data.get("reference") or ""),
            "event_type": str(payload.get("event", "")),
            "reference": str(data.get("reference", "")),
            "transaction_id": str(data.get("id", "")),
            "candidate_success": payload.get("event") == "charge.success" and data.get("status") == "success",
        }
    if gateway == "mtn_momo":
        return {
            "event_id": str(payload.get("financialTransactionId") or payload.get("externalId") or payload.get("referenceId") or ""),
            "event_type": "collection.status",
            "reference": str(payload.get("externalId") or ""),
            "transaction_id": str(payload.get("referenceId") or payload.get("financialTransactionId") or ""),
            "candidate_success": str(payload.get("status", "")).upper() == "SUCCESSFUL",
        }
    if gateway == "airtel_money":
        transaction = payload.get("transaction") or data.get("transaction") or data
        return {
            "event_id": str(transaction.get("id") or transaction.get("airtel_money_id") or ""),
            "event_type": "collection.status",
            "reference": str(transaction.get("reference") or payload.get("reference") or ""),
            "transaction_id": str(transaction.get("id") or ""),
            "candidate_success": str(transaction.get("status", "")).upper() in {"TS", "SUCCESS", "SUCCESSFUL"},
        }
    return {
        "event_id": str(payload.get("id") or data.get("id") or data.get("reference") or data.get("tx_ref") or ""),
        "event_type": str(payload.get("type") or payload.get("event") or ""),
        "reference": str(data.get("tx_ref") or data.get("reference") or ""),
        "transaction_id": str(data.get("id", "")),
        "candidate_success": data.get("status") in {"successful", "succeeded", "success"},
    }


@transaction.atomic
def process_webhook(gateway_name, raw_body, headers):
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise InvalidWebhook("Webhook body is not valid JSON.") from exc
    parsed = parse_event(gateway_name, payload)
    if not parsed["event_id"]:
        raise InvalidWebhook("Webhook event ID is missing.")
    signature_valid = verify_signature(gateway_name, raw_body, headers)
    event, created = PaymentWebhookEvent.objects.get_or_create(
        gateway=gateway_name,
        event_id=parsed["event_id"],
        defaults={"event_type": parsed["event_type"], "signature_valid": signature_valid, "payload": payload},
    )
    if not created and event.processed_at:
        return event, None, True
    if not signature_valid:
        event.outcome = "invalid_signature"
        event.error = "Webhook signature did not match."
        event.processed_at = timezone.now()
        event.save(update_fields=["outcome", "error", "processed_at"])
        raise InvalidWebhook("Invalid webhook signature.")
    if not parsed["candidate_success"]:
        event.outcome = "ignored"
        event.processed_at = timezone.now()
        event.save(update_fields=["outcome", "processed_at"])
        return event, None, False

    gateway = get_gateway(gateway_name)
    verification = gateway.verify(reference=parsed["reference"], transaction_id=parsed["transaction_id"])
    if not verification.get("successful"):
        raise InvalidWebhook("Gateway verification did not confirm a successful payment.")
    reference = verification.get("reference") or parsed["reference"]
    invoice = Invoice.objects.select_for_update().filter(number=reference).first()
    if not invoice:
        invoice = Invoice.objects.select_for_update().filter(gateway_ref=reference).first()
    if not invoice:
        raise InvalidWebhook("No invoice matches the verified transaction reference.")
    if verification.get("amount") is not None and int(verification["amount"]) != int(invoice.balance or invoice.amount):
        raise InvalidWebhook("Verified payment amount does not match the invoice balance.")
    if verification.get("currency") and verification["currency"] != invoice.currency:
        raise InvalidWebhook("Verified payment currency does not match the invoice currency.")

    payment = None
    if invoice.status != Invoice.Status.PAID:
        payment, receipt, invoice = confirm_invoice_payment(
            invoice=invoice,
            amount=invoice.balance,
            method=PaymentTransaction.Method.MOBILE_MONEY,
            reference=str(verification.get("provider_id") or reference),
            notes=f"Verified {gateway_name} webhook event {event.event_id}",
        )
    event.outcome = "confirmed"
    event.processed_at = timezone.now()
    event.save(update_fields=["outcome", "processed_at"])
    return event, invoice, False
