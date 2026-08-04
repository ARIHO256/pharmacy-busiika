# Provider Sandbox Acceptance

Provider adapters are not complete until the deploying organization has supplied approved sandbox credentials and passed callback, failure, and reconciliation tests.

## Required evidence

For each enabled provider record:

1. Credential owner and approval reference.
2. Sandbox endpoint and account identifier, excluding secrets from reports.
3. Successful request and provider correlation ID.
4. Signed callback/webhook verification.
5. Duplicate callback/idempotency test.
6. Timeout, retry, and permanent-failure test.
7. Reconciliation or delivery-status evidence.
8. Secret rotation test.
9. Provider outage/failover behavior.
10. Data-retention and privacy review.

## Provider groups

- MTN Mobile Money, Airtel Money, Flutterwave, and/or Paystack.
- Email, SMS, WhatsApp, FCM, and APNs.
- Zoom or approved telemedicine provider.
- Private S3-compatible object storage and malware scanner.
- Orthanc/PACS, DICOM modality, and viewer authorization.
- Regulator and insurer connections.
- Mapping/routing provider for ambulance ETA.
- Kafka/Redpanda, RabbitMQ, and partner webhooks.

Run:

```bash
python3 scripts/provider-sandbox-check.py
```

A successful configuration check is necessary but not sufficient. Store the real transaction evidence in the release-acceptance record or the organization’s controlled evidence repository.
