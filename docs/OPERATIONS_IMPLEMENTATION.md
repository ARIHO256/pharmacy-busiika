# Operational workflows delivery — 4 November 2026

This delivery extends the existing Django application rather than replacing its
clinical or accounting records. Payments are excluded. All original screens retain
their presentation; new workflow pages and navigation entries were explicitly
approved in the implementation conversation.

## Delivered application behavior

| Area | Implemented behavior | External or specialist work still required |
|---|---|---|
| Hospital | Admissions, one active admission per patient/bed, transfers, signed discharge summary, follow-up, automatic bed release and dose cancellation | Hospital policy validation, ward-specific processes, discharge-document standards |
| Medication administration | Signed-prescription matching, scheduled doses, nurse/doctor administration, refusal/withholding reasons, duplicate-administration protection | Clinically validated scheduling protocols, controlled-dose calculations and full inpatient eMAR validation |
| Procedures | Theatre/patient/surgeon conflict checks, cross-facility clinician locking, scheduled/in-progress/completed/cancelled history | Theatre policy, anesthesia and perioperative documentation |
| Pharmacy | Batch receipts, expiry-aware stock, FEFO online allocation, immutable API movement register, quarantine, irreversible recall, temperature excursions, independent controlled-stock witness, prescription-quantity enforcement | Existing stock reconciliation, genuine batch data, pharmacy SOPs, formulary and jurisdiction-specific controlled-drug requirements |
| Insurance | Configurable service benefits, annual limits, preauthorization decisions, immutable claim assessment snapshots, covered/patient shares, assessment reconciliation totals | Insurer contracts, benefit catalogues and operational enrollment validation; no settlement or money movement added |
| Patient identity | Separate person/account linkage, identifier namespaces, demographic match candidates, reasoned merge/unmerge with original clinical ownership retained | Validated probabilistic matching, authoritative identity sources, national identifier policies |
| Referrals | Named receiving organization, acceptance, assignment, scheduling, start, outcome/decline/cancel, optimistic version checks | Actual receiving-facility agreements and clinical workflow validation |
| Imaging | Orders, modality/site, scheduling, acquisition UID, signed clinician reports, bounded DICOMweb study-metadata adapter | PACS/DICOM archive, acquisition hardware, radiologist workflow validation and a diagnostic image viewer; this delivery is not a diagnostic viewer |
| Messaging | Authenticated WebSocket refresh hints, origin and participant checks, token expiry, HTTP fallback, incremental sync, read/delivery timestamps, idempotent text-message retries | Redis and ASGI deployment; existing message attachments are not migrated into the new private-document storage |
| Video | Random session rooms, private Jitsi JWTs, independent participant recording consent, quality-event records, session closure | A private Jitsi deployment and provider enforcement of recording permissions; the application does not itself record calls or implement provider QoS/SLA monitoring |
| Offline facilities | Encrypted SQLite capture tool, encrypted server inbox, idempotency checks, clinician preview/review, append-only application of observations/nursing notes | Facility machines, separately managed keys, identity verification and operational synchronization testing; this is not a full offline replica of every portal |
| Terminology | Configured FHIR R4 CodeSystem `$lookup` and ValueSet `$expand` adapters alongside the existing local catalogue | A terminology server and licensed, maintained clinical vocabularies |
| Health exchange | Audited, explicit data-sharing-consent-gated summary delivery to a configured partner | Approved national implementation guide, partner agreement, conformance tests and credentials; no national certification is claimed |
| Clinical rules | Versioned evidence references, independent publication approval, deactivation, medication-pair evaluation and explicit knowledge-coverage reporting | Licensed, clinically reviewed interaction content and professional validation; an empty catalogue is never presented as a complete safety check |
| Workers | Celery/Redis configuration, scheduled reminders, inventory expiry refresh, leased outbox delivery, bounded retries, dead-letter state, signed idempotent webhook transport | A running broker, workers, scheduler, monitoring and receiving service |
| SMS/push | Configurable authenticated gateway contracts, generic non-clinical message bodies, provider acknowledgement IDs, signed delivery callbacks, retries and preference rechecks | Real SMS/push gateways and push-device registration/recipient mapping at the gateway |
| Private documents | Scan-before-store, fail-closed ClamAV adapter, private local/S3 storage, authorized downloads, 60-second signed links with access rechecks | Running ClamAV, private S3 bucket/IAM where used, retention policies and migration/scanning of existing legacy uploads |
| Research | Independently approved materialized monthly aggregates, active research consent filtering, distinct-patient thresholds and small-cell suppression | A full research warehouse/OMOP pipeline, approved research protocols and formal disclosure-risk review |
| Copilot | Evaluated model registry, allowlisted administrative provider adapters, independent activation, draft review/rejection, no automatic clinical-record publication | Approved inference provider, governance/evaluation evidence and clinical safety review; diagnostic/treatment AI is not enabled |

These distinctions are deliberate. A configured adapter is executable application
code, but installing it does not provision an external service, license a dataset
or establish clinical/regulatory conformity.

## Portal entry points

- `/facility/operations`: facility logistics and workflow oversight.
- `/doctor/operations`: clinician admission/discharge, scheduled medication,
  procedures, referrals, imaging and offline review.
- `/nurse/operations`: admission and transfer support, scheduled administration
  and offline review. Prescribing/discharge/report signing remain clinician gated.
- `/lab-staff/operations`: imaging worklist and acquisition support.
- `/pharmacy/stock-control` and `/pharmacist/stock-control`: batch inventory,
  movement registers, expiry, cold-chain quarantine and recall.
- `/insurance/benefits`: service benefits, preauthorizations and assessments.
- `/admin/operations`: identity links/merge review, clinical-rule governance,
  private documents, research requests and administrative copilot governance.

Existing screens and routes remain available. Clinical and administrative role
checks run at the API regardless of which controls a browser displays.

## API contract

The new router is mounted at `/api/operations/` and `/api/v1/operations/`.
Lists return `{count, next, previous, results}` with a default page size of 100 and
maximum of 200. Workflow resources deliberately do not expose general DELETE or
arbitrary status PATCH operations. Organization IDs are canonical registry IDs,
not the legacy provider-account IDs used by older service endpoints.

| Resource | Important operations |
|---|---|
| `context/` | GET accessible organizations, scoped pick lists and capabilities |
| `admissions/` | POST; `/{id}/transition/` with `action`, current `version` and transfer bed or discharge summary |
| `medication-schedules/` | POST signed-prescription-compatible schedule; `/{id}/administer/` with status and notes |
| `procedures/` | POST future booking; `/{id}/transition/` |
| `medicine-batches/` | POST empty batch; `/{id}/movement/`, `transition/`, `register/` |
| `benefits/` | POST; `/{id}/configure/` PATCH with benefit fields |
| `authorizations/` | POST; `/{id}/decide/` |
| `claim-assessments/` | POST; `/{id}/assess/`; collection `reconciliation/` |
| `identities/` | POST; `/{id}/link/`, `identifier/`, `candidates/`, `merge/`, `unmerge/` |
| `referrals/` | POST existing sent referral plus receiving organization; `/{id}/transition/` |
| `imaging/` | POST; `/{id}/transition/`; `/{id}/study/` for linked study metadata |
| `clinical-rules/` | POST draft rule; `/{id}/approve/`, `deactivate/`; collection `evaluate/` |
| `offline-nodes/` | POST; `/{id}/submit/`, `changes/`, `preview/?change={id}`, `review/` |
| `documents/` | multipart POST; `/{id}/download/` and POST `access-link/` |
| `research-exports/` | POST purpose; independent `/{id}/approve/` |
| `copilot-models/` | POST evaluated model; independent `/{id}/approve/`, `deactivate/` |
| `copilot-drafts/` | POST approved model and source; `/{id}/review/` |
| `terminology/lookup/`, `terminology/expand/` | GET terminology queries |
| `hie/patients/{patient_id}/export/` | POST consent-gated summary to configured partner |
| `video/{appointment_id}/` | GET join; POST recording consent, quality or end |
| `notification-callback/` | Signed delivery status POST from the gateway |

Stock movements require an idempotency UUID `reference`; retries must preserve it.
Received/returned quantities are positive, dispensed/destroyed quantities negative.
Controlled movements require a distinct verified witness at the same organization;
dispensing also requires the patient and a matching signed `prescription_item`.
The prescription's remaining quantity is updated in the same transaction.

For legacy stock, reconcile untracked inventory to zero before creating the first
batch, then receive the physical stock into identified batches with correct expiry
dates. No batch numbers or expiry dates are fabricated during migration.

Identity merging changes a canonical identity link only. It does not rewrite
patient foreign keys, collapse logins or automatically broaden consent/access.

## Messaging and synchronization

WebSockets connect to `/ws/conversations/{conversation_id}/`. The first JSON frame
must be `{"type":"authenticate","access_token":"<access JWT>"}` within ten
seconds. Tokens never appear in WebSocket URLs. After `ready`, `message.created`
and `message.receipt` carry only a message ID; authorized HTTP reads retrieve
content. Origin, account activity and participation checks remain enforced.

Existing HTTP message creation accepts optional `client_id` UUIDs. New
`GET /api/v1/conversations/{id}/sync/?after={message_id}` returns up to 200 messages,
a cursor and `has_more`. POST to the same URL with `through_id` and
`phase: delivered|read` records incoming-message receipts.

## External gateway contracts

All outbound URLs are server-controlled, HTTPS-only in production, time bounded,
redirect forbidden and response-size bounded. Do not put credentials in URLs.

SMS/push gateways receive an idempotent POST containing delivery ID, channel,
recipient, user ID and a generic sign-in prompt, authenticated with a bearer token.
They must return JSON containing `id`. The gateway is responsible for mapping
users to registered push devices and integrating its actual carrier/push provider.

Delivery callbacks send `provider_reference` and `status: delivered|failed`.
`X-MyDoctor-Timestamp` is epoch seconds; `X-MyDoctor-Signature` is hex HMAC-SHA256
over `timestamp + '.' + exact_request_body` using `NOTIFICATION_CALLBACK_SECRET`.
Callbacks outside five minutes are rejected.

Outbox receivers get an envelope containing canonical JSON in `payload`, a stable
`Idempotency-Key` and the same timestamp/signature construction using
`OUTBOX_WEBHOOK_SECRET`. Metadata excludes clinical payload content. Receivers
must deduplicate by event ID. Delivery is at least once, not exactly once.

The approved copilot gateway receives the pinned model name/version, the
administrative task instructions and user-supplied source text. It returns
`{"draft":"..."}`. No provider is enabled by default. Do not configure a provider
for patient information without the appropriate approved data-processing controls.

## Local setup and deployment

From `backend/`, install `requirements.txt`, then run:

```bash
python manage.py migrate
python manage.py check
python manage.py test operations
python manage.py runserver
```

The Django requirement is now 5.2 LTS, including Python 3.14 compatibility.
Daphne supplies ASGI handling for development; production must also use ASGI.
Existing HTTP response shapes remain compatible with the original portals.

For background processing, set `REDIS_URL` and run a worker and exactly one beat
scheduler:

```bash
celery -A config worker --loglevel=INFO
celery -A config beat --loglevel=INFO
```

`backend/compose.yaml` provides API, PostgreSQL, Redis, worker, scheduler and
ClamAV services. Supply a real `DJANGO_SECRET_KEY`, `DB_PASSWORD`, allowed hosts,
origins and provider settings in `backend/.env`. Run migrations as a one-off
deployment step before serving traffic:

```bash
docker compose build
docker compose run --rm api python manage.py migrate
docker compose up -d
```

The API binds only to localhost on the host. Place a TLS reverse proxy in front
of it and forward WebSocket upgrades for `/ws/`. Configure trusted proxy headers
only behind that trusted proxy. Use managed PostgreSQL TLS and a private broker
network in a production environment. Pin deployment images to reviewed digests.
Docker, Redis, ClamAV, S3, PACS, Jitsi and partner services were not provisioned by
this coding session.

Set `CLAMAV_HOST` before uploading new private documents. With no scanner, uploads
return 503 and do not store files. Local private storage lives outside public
`MEDIA_ROOT`. S3 support uses a private bucket, server-side encryption, no public
ACL and short-lived signing configuration. Legacy uploads retain their existing
storage behavior and require a separate migration/retention project.

Generate separate Fernet keys for `OFFLINE_ENCRYPTION_KEY` (server inbox) and
`FACILITY_NODE_KEY` (each facility machine). Keep keys outside database backups.
The capture tool stores encrypted payloads in a restrictive-permission SQLite file:

```bash
python tools/facility_node.py enqueue --database /secure/ward.sqlite3 --server https://your-api.example --node 1 < observation.json
python tools/facility_node.py sync --database /secure/ward.sqlite3 --server https://your-api.example --node 1
```

Synchronization also needs `FACILITY_NODE_ACCESS_TOKEN` in the environment. Tokens
are not stored in SQLite. Submitted records remain pending until a clinician
reviews and applies or rejects them. Expired or suspended access cannot silently
apply queued changes.

## Verification and limits

Automated coverage includes role/organization isolation, bed conflicts and
transfers, signed-prescription matching, duplicate administration, procedure
overlaps, stock overselling/rollback, controlled-stock witnesses and quantity
limits, recalls/temperature quarantine, annual insurance limits, identity
reversal, referral/imaging transitions, encrypted offline review, document
signing/access revocation, consent-gated HIE, provider failure, callback signing,
copilot review isolation and WebSocket authentication.

SQLite verifies application behavior and constraints here; PostgreSQL concurrency,
external-provider contracts, backup restoration, image rendering, clinical content
and regulatory conformance still require their real deployment environments.
The pre-existing payment tests are tracked separately because payments were
explicitly excluded from the requested work.

## Primary implementation references

- [Django transaction locking](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update)
- [Channels authentication](https://channels.readthedocs.io/en/stable/topics/authentication.html)
- [Celery Django setup](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html)
- [Private S3 storage options](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)
- [FHIR R4 terminology lookup](https://www.hl7.org/fhir/R4/codesystem-operation-lookup.html)
- [FHIR R4 value-set expansion](https://www.hl7.org/fhir/R4/valueset-operation-expand.html)

## Visit-linked laboratory handoffs and pharmacy corrections

A front-desk user can assign a verified doctor or nurse in **Patient Flow**. The
assigned doctor can select the visit in **Laboratory Referrals** and order a test
from a verified laboratory. Reception and the receiving lab can record arrival
against the same order. The reception queue shows destination, order reference,
arrival and status. Clinical results appear in the authorized review workspace.
After a result is released, the assigned doctor can resume the consultation
from the result review dialog.

Set `LAB_CRITICAL_ESCALATION_MINUTES` to the response window approved for the
deployment. The value `0` disables timed escalation. Run Celery worker and
beat for the scheduled check. A current released critical result with no
acknowledgement raises one in-app escalation to the receiving lab account and
eligible clinicians. The clinical review dialog shows when it was escalated.

A verified pharmacist can reverse a dispensing movement recorded against a
prepared order before the medicine leaves pharmacy custody. A reason and
custody confirmation are required, and controlled batches require an independent
witness. The original and reversal remain in the movement register. Patient
returns and substituting a different prescribed medicine require separate
clinical and pharmacy procedures.
