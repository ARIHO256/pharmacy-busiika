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
        MTN_MOMO = "mtn_momo", "MTN Mobile Money"
        AIRTEL_MONEY = "airtel_money", "Airtel Money"

    number = models.CharField(max_length=30, unique=True, blank=True)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
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


class PaymentWebhookEvent(models.Model):
    gateway = models.CharField(max_length=24)
    event_id = models.CharField(max_length=180)
    event_type = models.CharField(max_length=80, blank=True, default="")
    signature_valid = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)
    outcome = models.CharField(max_length=40, blank=True, default="")
    error = models.TextField(blank=True, default="")
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [models.UniqueConstraint(fields=["gateway", "event_id"], name="unique_gateway_webhook_event")]
        indexes = [models.Index(fields=["gateway", "received_at"])]


class InvoiceAdjustment(models.Model):
    class Type(models.TextChoices):
        CREDIT = "credit", "Credit note"
        DEBIT = "debit", "Debit note"
        DISCOUNT = "discount", "Discount"
        WRITE_OFF = "write_off", "Write-off"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        APPLIED = "applied", "Applied"

    number = models.CharField(max_length=40, unique=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="adjustments")
    adjustment_type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.PositiveBigIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_invoice_adjustments")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_invoice_adjustments")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"ADJ-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class RefundRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    number = models.CharField(max_length=40, unique=True, blank=True)
    payment = models.ForeignKey(PaymentTransaction, on_delete=models.PROTECT, related_name="refund_requests")
    amount = models.PositiveBigIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_refunds")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_refunds")
    gateway_reference = models.CharField(max_length=180, blank=True, default="")
    error = models.TextField(blank=True, default="")
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"REF-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class FinancialPeriod(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSING = "closing", "Closing"
        CLOSED = "closed", "Closed"
        LOCKED = "locked", "Locked"

    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="financial_periods")
    name = models.CharField(max_length=120)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_financial_periods")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="closed_financial_periods")
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="unique_financial_period_name")]
        indexes = [models.Index(fields=["organization", "status", "starts_on"], name="pay_period_org_status")]

    def clean(self):
        if self.ends_on and self.starts_on and self.ends_on < self.starts_on:
            from django.core.exceptions import ValidationError
            raise ValidationError({"ends_on": "The financial period must end on or after its start date."})


class DepartmentBudget(models.Model):
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="department_budgets")
    department = models.ForeignKey("workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="budgets")
    period = models.ForeignKey(FinancialPeriod, on_delete=models.PROTECT, related_name="budgets")
    category = models.CharField(max_length=120, default="operating")
    amount = models.PositiveBigIntegerField(default=0)
    committed_amount = models.PositiveBigIntegerField(default=0)
    spent_amount = models.PositiveBigIntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_department_budgets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "department", "category"]
        constraints = [models.UniqueConstraint(fields=["period", "department", "category"], name="unique_department_budget_category")]

    @property
    def available_amount(self):
        return max(int(self.amount) - int(self.committed_amount) - int(self.spent_amount), 0)


class ApprovalLimit(models.Model):
    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="financial_approval_limits")
    role_code = models.CharField(max_length=60)
    operation_type = models.CharField(max_length=60, default="expense")
    maximum_amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="UGX")
    requires_second_approval = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "role_code", "operation_type"]
        constraints = [models.UniqueConstraint(fields=["organization", "role_code", "operation_type", "currency"], name="unique_financial_approval_limit")]


class Expense(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="expenses")
    department = models.ForeignKey("workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses")
    vendor = models.CharField(max_length=180, blank=True, default="")
    category = models.CharField(max_length=100, default="operating")
    description = models.TextField()
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="UGX")
    incurred_on = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    reference = models.CharField(max_length=160, blank=True, default="")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_expenses")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_expenses")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-incurred_on", "-id"]
        indexes = [models.Index(fields=["organization", "status", "incurred_on"], name="pay_expense_org_status")]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"EXP-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class SupplierInvoice(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        VERIFIED = "verified", "Verified"
        APPROVED = "approved", "Approved"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        DISPUTED = "disputed", "Disputed"
        VOID = "void", "Void"

    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="supplier_invoices")
    supplier_name = models.CharField(max_length=220)
    invoice_number = models.CharField(max_length=100)
    amount = models.PositiveBigIntegerField()
    paid_amount = models.PositiveBigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="UGX")
    invoice_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    reference = models.CharField(max_length=160, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_supplier_invoices")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_supplier_invoices")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["organization", "supplier_name", "invoice_number"], name="unique_supplier_invoice")]
        indexes = [models.Index(fields=["organization", "status", "due_date"], name="pay_supplier_due_status")]

    @property
    def balance(self):
        return max(int(self.amount) - int(self.paid_amount), 0)


class ReconciliationRun(models.Model):
    class Kind(models.TextChoices):
        BANK = "bank", "Bank"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        GATEWAY = "gateway", "Payment gateway"
        CASH = "cash", "Cash drawer"
        INSURANCE = "insurance", "Insurance settlement"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In progress"
        BALANCED = "balanced", "Balanced"
        VARIANCE = "variance", "Variance"
        CLOSED = "closed", "Closed"

    number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="reconciliation_runs")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    expected_amount = models.BigIntegerField(default=0)
    actual_amount = models.BigIntegerField(default=0)
    variance = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    evidence = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_reconciliations")
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_reconciliations")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        indexes = [models.Index(fields=["organization", "kind", "status"], name="pay_recon_org_kind")]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"REC-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        self.variance = int(self.actual_amount) - int(self.expected_amount)
        if self.status not in {self.Status.CLOSED, self.Status.IN_PROGRESS}:
            self.status = self.Status.BALANCED if self.variance == 0 else self.Status.VARIANCE
        super().save(*args, **kwargs)


class PayerAllocation(models.Model):
    class PayerType(models.TextChoices):
        PATIENT = "patient", "Patient"
        INSURANCE = "insurance", "Insurance"
        EMPLOYER = "employer", "Employer"
        SPONSOR = "sponsor", "Sponsor"
        CREDIT = "credit", "Patient credit"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payer_allocations")
    payer_type = models.CharField(max_length=20, choices=PayerType.choices)
    payer_reference = models.CharField(max_length=160, blank=True, default="")
    allocated_amount = models.PositiveBigIntegerField()
    paid_amount = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, default="allocated")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_payer_allocations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["invoice", "payer_type"]
