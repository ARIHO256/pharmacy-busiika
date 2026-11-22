import os

from django.conf import settings


class MockGateway:
    """Development gateway: initiation returns a checkout URL pointing at the
    mock webhook endpoint, which marks the invoice paid."""

    name = "mock"

    def initiate(self, invoice, phone=None):
        return {
            "ref": f"MOCK-{invoice.number}",
            "checkout_url": f"/api/payments/webhook/mock/{invoice.number}/",
        }


class FlutterwaveGateway:
    name = "flutterwave"

    def __init__(self):
        self.secret_key = os.environ.get("FLUTTERWAVE_SECRET_KEY", "")
        self.public_key = os.environ.get("FLUTTERWAVE_PUBLIC_KEY", "")

    def initiate(self, invoice, phone=None):
        raise NotImplementedError("configure keys")


class PaystackGateway:
    name = "paystack"

    def __init__(self):
        self.secret_key = os.environ.get("PAYSTACK_SECRET_KEY", "")

    def initiate(self, invoice, phone=None):
        raise NotImplementedError("configure keys")


def get_gateway(name=None):
    if name is None:
        name = "mock" if getattr(settings, "MOCK_PAYMENTS", False) else "mock"
    gateways = {
        "mock": MockGateway,
        "flutterwave": FlutterwaveGateway,
        "paystack": PaystackGateway,
    }
    try:
        return gateways[name]()
    except KeyError:
        raise ValueError(f"Unknown gateway: {name}")
