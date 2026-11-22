import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        VOID = "void", "Void"

    class Gateway(models.TextChoices):
        MOCK = "mock", "Mock"
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        CARD = "card", "Card"
        BANK = "bank", "Bank transfer"
        INSURANCE = "insurance", "Insurance"
        FLUTTERWAVE = "flutterwave", "Flutterwave"
        PAYSTACK = "paystack", "Paystack"

    number = models.CharField(max_length=30, unique=True, blank=True)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
        null=True,
        blank=True,
    )
    organization = models.ForeignKey(
        "registry.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    visit = models.ForeignKey("workforce.PatientVisit", on_delete=models.PROTECT, null=True, blank=True, related_name="invoices")
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_invoices",
    )
    amount = models.PositiveBigIntegerField(default=0)
    discount_amount = models.PositiveBigIntegerField(default=0)
    tax_amount = models.PositiveBigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="UGX")
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING
    )
    gateway = models.CharField(
        max_length=24, choices=Gateway.choices, default=Gateway.MOCK
    )
    gateway_ref = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
            models.Index(fields=["patient", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"INV-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)

    @property
    def paid_amount(self):
        return sum(
            payment.amount
            for payment in self.payments.filter(status=PaymentTransaction.Status.CONFIRMED)
        )

    @property
    def balance(self):
        return max(int(self.amount) - int(self.paid_amount), 0)

    def recalculate_amount(self, save=True):
        subtotal = sum(item.line_total for item in self.items.all())
        self.amount = max(subtotal + int(self.tax_amount) - int(self.discount_amount), 0)
        if save:
            self.save(update_fields=["amount", "updated_at"])
        return self.amount

    def __str__(self):
        return f"{self.number} ({self.status})"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=80, blank=True, default="")
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0.01)]
    )
    unit_price = models.PositiveBigIntegerField()
    discount_amount = models.PositiveBigIntegerField(default=0)
    line_total = models.PositiveBigIntegerField(default=0)
    service_type = models.CharField(max_length=60, blank=True, default="")
    source_id = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        gross = int(self.quantity * self.unit_price)
        self.line_total = max(gross - int(self.discount_amount), 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} — {self.line_total}"


class PaymentTransaction(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        CARD = "card", "Card"
        BANK = "bank", "Bank transfer"
        WALLET = "wallet", "Wallet"
        INSURANCE = "insurance", "Insurance"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        VOID = "void", "Void"

    number = models.CharField(max_length=30, unique=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.PositiveBigIntegerField()
    method = models.CharField(max_length=24, choices=Method.choices)
    reference = models.CharField(max_length=140, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_payments",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["invoice", "status"])]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"PAY-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number


class Receipt(models.Model):
    number = models.CharField(max_length=30, unique=True, blank=True)
    payment = models.OneToOneField(
        PaymentTransaction, on_delete=models.PROTECT, related_name="receipt"
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"RCT-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number


class CashierShift(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cashier_shifts"
    )
    organization = models.ForeignKey(
        "registry.Organization", on_delete=models.PROTECT, related_name="cashier_shifts"
    )
    opening_float = models.PositiveBigIntegerField(default=0)
    expected_cash = models.PositiveBigIntegerField(default=0)
    closing_cash = models.PositiveBigIntegerField(null=True, blank=True)
    variance = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-opened_at"]
        indexes = [models.Index(fields=["organization", "status", "opened_at"])]

    def __str__(self):
        return f"Shift {self.id} — {self.cashier}"


class Subscription(models.Model):
    class Plan(models.TextChoices):
        BASIC = "basic", "Basic"
        PREMIUM = "premium", "Premium"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.BASIC)
    active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user_id} {self.plan}"


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payouts",
    )
    amount = models.IntegerField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payout {self.pk} to doctor {self.doctor_id} ({self.status})"


class LedgerAccount(models.Model):
    class Type(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        REVENUE = "revenue", "Revenue"
        EXPENSE = "expense", "Expense"
        EQUITY = "equity", "Equity"

    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=Type.choices)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_accounts",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(models.Model):
    reference = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=500)
    source_type = models.CharField(max_length=80, blank=True, default="")
    source_id = models.CharField(max_length=100, blank=True, default="")
    currency = models.CharField(max_length=3, default="UGX")
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at"]

    @property
    def total_debits(self):
        return sum(p.amount for p in self.postings.filter(direction="debit"))

    @property
    def total_credits(self):
        return sum(p.amount for p in self.postings.filter(direction="credit"))

    @property
    def is_balanced(self):
        return self.total_debits == self.total_credits and self.total_debits > 0

    def __str__(self):
        return self.reference


class Posting(models.Model):
    class Direction(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    entry = models.ForeignKey(
        JournalEntry, on_delete=models.PROTECT, related_name="postings"
    )
    account = models.ForeignKey(
        LedgerAccount, on_delete=models.PROTECT, related_name="postings"
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    amount = models.PositiveBigIntegerField()
    memo = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="posting_amount_positive"
            )
        ]

    def __str__(self):
        return f"{self.direction} {self.amount} {self.account.code}"
