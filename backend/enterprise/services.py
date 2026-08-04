import csv
import hashlib
import hmac
import io
import json
import math
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone

from enterprise.access import active_role

from .models import (
    ContentEntry, DeadLetterEvent, EnterpriseRecord, EventDelivery, FHIRResource,
    ImagingStudy, MedicationInteraction, MedicationKnowledge, NotificationProvider,
    ReportRun, ResourceAttachment, SecurityOperation, TelemedicineParticipant,
    TelemedicineSession, VerificationAutomation,
)


class EnterpriseServiceError(RuntimeError):
    pass


def http_json(url, *, method="GET", data=None, headers=None, timeout=30):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise EnterpriseServiceError(f"HTTP {exc.code}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise EnterpriseServiceError(f"Connection failed: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Telemedicine providers
# ---------------------------------------------------------------------------
class JitsiProvider:
    def create(self, session):
        base = os.getenv("JITSI_BASE_URL", "https://meet.jit.si").rstrip("/")
        room = f"mydoctor-{session.public_id.hex}"
        return {"external_id": room, "join_url": f"{base}/{room}", "host_url": f"{base}/{room}#config.prejoinPageEnabled=false"}


class ZoomProvider:
    def _token(self):
        account_id = os.getenv("ZOOM_ACCOUNT_ID", "")
        client_id = os.getenv("ZOOM_CLIENT_ID", "")
        client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")
        if not all((account_id, client_id, client_secret)):
            raise EnterpriseServiceError("Zoom Server-to-Server OAuth credentials are incomplete.")
        basic = __import__("base64").b64encode(f"{client_id}:{client_secret}".encode()).decode()
        url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={urllib.parse.quote(account_id)}"
        request = urllib.request.Request(url, method="POST", headers={"Authorization": f"Basic {basic}"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())["access_token"]
        except Exception as exc:
            raise EnterpriseServiceError(f"Zoom token request failed: {exc}") from exc

    def create(self, session):
        token = self._token()
        user_id = os.getenv("ZOOM_HOST_USER_ID", "me")
        payload = {
            "topic": f"MyDoctor consultation {session.public_id}",
            "type": 2,
            "start_time": session.scheduled_start.isoformat() if session.scheduled_start else None,
            "duration": int(os.getenv("TELEMEDICINE_DEFAULT_DURATION_MINUTES", "30")),
            "timezone": os.getenv("DJANGO_TIME_ZONE", "Africa/Kampala"),
            "settings": {
                "waiting_room": session.waiting_room_enabled,
                "join_before_host": False,
                "mute_upon_entry": True,
                "auto_recording": "cloud" if session.recording_enabled else "none",
                "approval_type": 0,
            },
        }
        _, data = http_json(
            f"https://api.zoom.us/v2/users/{urllib.parse.quote(user_id)}/meetings",
            method="POST",
            data=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"external_id": str(data.get("id", "")), "join_url": data.get("join_url", ""), "host_url": data.get("start_url", "")}


def create_telemedicine_session(appointment, provider=None):
    provider_name = provider or os.getenv("TELEMEDICINE_PROVIDER", "jitsi").lower()
    session, _ = TelemedicineSession.objects.get_or_create(
        appointment=appointment,
        defaults={"provider": provider_name, "scheduled_start": appointment.start_time},
    )
    adapter = ZoomProvider() if provider_name == "zoom" else JitsiProvider()
    result = adapter.create(session)
    session.provider = provider_name
    session.external_id = result["external_id"]
    session.join_url = result["join_url"]
    session.host_url = result["host_url"]
    session.save(update_fields=["provider", "external_id", "join_url", "host_url"])
    for user, role in ((appointment.patient, "patient"), (appointment.doctor, "clinician")):
        TelemedicineParticipant.objects.get_or_create(session=session, user=user, defaults={"role": role})
    return session


# ---------------------------------------------------------------------------
# File security / malware scanning
# ---------------------------------------------------------------------------
def clamav_scan(path):
    host = os.getenv("CLAMAV_HOST", "clamav")
    port = int(os.getenv("CLAMAV_PORT", "3310"))
    timeout = int(os.getenv("CLAMAV_TIMEOUT_SECONDS", "30"))
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(b"zINSTREAM\0")
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
        sock.sendall((0).to_bytes(4, "big"))
        response = b""
        while not response.endswith(b"\0"):
            part = sock.recv(4096)
            if not part:
                break
            response += part
    result = response.decode("utf-8", errors="replace").strip("\0")
    return {"clean": result.endswith("OK"), "response": result}


def scan_attachment(attachment):
    try:
        scan = clamav_scan(attachment.file.path)
        attachment.malware_status = "clean" if scan["clean"] else "infected"
    except Exception as exc:
        if os.getenv("ALLOW_SCAN_FAILURE", "false").lower() in {"1", "true", "yes"}:
            attachment.malware_status = "error"
        else:
            attachment.malware_status = "infected"
        scan = {"clean": False, "response": str(exc)}
    attachment.save(update_fields=["malware_status"])
    SecurityOperation.objects.create(
        operation_type="upload_scan",
        status="completed",
        severity="critical" if not scan["clean"] else "low",
        title=f"Attachment scan: {attachment.title}",
        description=scan["response"],
        scope={"attachment_id": attachment.id, "checksum": attachment.checksum_sha256},
        findings=[] if scan["clean"] else [{"type": "malware_or_scan_failure", "detail": scan["response"]}],
        completed_at=timezone.now(),
        owner=attachment.uploaded_by,
    )
    return scan


# ---------------------------------------------------------------------------
# Verification automation
# ---------------------------------------------------------------------------
def image_quality(document):
    try:
        from PIL import Image, ImageStat
        image = Image.open(document)
        width, height = image.size
        grayscale = image.convert("L")
        contrast = ImageStat.Stat(grayscale).stddev[0]
        resolution_score = min(100, (width * height) / (1200 * 900) * 100)
        contrast_score = min(100, contrast / 45 * 100)
        exif = image.getexif() or {}
        software = str(exif.get(305, ""))
        metadata = {
            "width": width,
            "height": height,
            "contrast": round(contrast, 2),
            "format": image.format,
            "mode": image.mode,
            "editing_software": software,
        }
        return round((resolution_score * 0.6) + (contrast_score * 0.4), 2), metadata
    except Exception:
        return None, {}


def _document_checksum(document):
    if not document:
        return ""
    digest = hashlib.sha256()
    try:
        document.open("rb")
        for chunk in document.chunks():
            digest.update(chunk)
        document.seek(0)
        return digest.hexdigest()
    except Exception:
        try:
            with open(document.path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except Exception:
            return ""


def _text_similarity(left, right):
    left = " ".join(str(left or "").lower().split())
    right = " ".join(str(right or "").lower().split())
    if not left or not right:
        return 0
    return round(SequenceMatcher(None, left, right).ratio() * 100, 2)


def external_ocr(document_path):
    endpoint = os.getenv("DOCUMENT_OCR_ENDPOINT", "")
    if not endpoint:
        return {}
    token = os.getenv("DOCUMENT_OCR_TOKEN", "")
    with open(document_path, "rb") as handle:
        encoded = __import__("base64").b64encode(handle.read()).decode()
    _, data = http_json(endpoint, method="POST", data={"content_base64": encoded}, headers={"Authorization": f"Bearer {token}"} if token else {})
    return data


def regulator_lookup(scan, identifier, issuer):
    connector = scan.credential and scan.credential.practitioner and scan.credential.practitioner.role
    from .models import RegulatorConnector
    row = RegulatorConnector.objects.filter(active=True).filter(Q(profession=connector) | Q(authority__iexact=issuer)).first()
    if not row or not row.base_url:
        return {"status": "not_configured"}
    query = row.lookup_template or {"license_number": "{identifier}"}
    params = {key: str(value).replace("{identifier}", identifier) for key, value in query.items()}
    headers = {}
    token = os.getenv(row.credentials_reference, "") if row.credentials_reference else ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    _, data = http_json(f"{row.base_url}?{urllib.parse.urlencode(params)}", headers=headers)
    row.last_checked_at = timezone.now()
    row.save(update_fields=["last_checked_at"])
    return data


@transaction.atomic
def execute_verification_scan(scan):
    scan.status = "processing"
    scan.save(update_fields=["status"])
    document = None
    expected_name = ""
    expected_identifier = ""
    issuer = ""
    if scan.credential_id:
        document = scan.credential.document
        expected_name = scan.credential.practitioner.display_name
        expected_identifier = scan.credential.identifier
        issuer = scan.credential.issuer
    elif scan.organization_id:
        document = scan.organization.license_document
        expected_name = scan.organization.legal_name
        expected_identifier = scan.organization.license_number
        issuer = scan.organization.issuing_authority
    fields = {}
    quality = None
    quality_meta = {}
    if document:
        try:
            quality, quality_meta = image_quality(document)
            fields = external_ocr(document.path)
        except Exception as exc:
            fields = {"error": str(exc)}
    extracted_name = str(fields.get("name") or fields.get("holder_name") or "")
    extracted_identifier = str(fields.get("license_number") or fields.get("identifier") or "")
    name_match = _text_similarity(extracted_name, expected_name)
    normalized_extracted_id = "".join(ch for ch in extracted_identifier.lower() if ch.isalnum())
    normalized_expected_id = "".join(ch for ch in expected_identifier.lower() if ch.isalnum())
    id_match = 100 if normalized_extracted_id and normalized_extracted_id == normalized_expected_id else _text_similarity(normalized_extracted_id, normalized_expected_id)
    if not extracted_name and not extracted_identifier:
        match_score = None
    else:
        match_score = round(name_match * 0.4 + id_match * 0.6, 2)
    flags = []
    checksum = _document_checksum(document)
    if quality is not None and quality < 55:
        flags.append("low_document_quality")
    editing_software = str(quality_meta.get("editing_software") or "").lower()
    if any(marker in editing_software for marker in ("photoshop", "gimp", "lightroom", "canva")):
        flags.append("document_editing_software_detected")
    if checksum:
        for previous in VerificationAutomation.objects.filter(status="completed").exclude(pk=scan.pk).order_by("-completed_at")[:500]:
            if (previous.extracted_fields or {}).get("document_checksum_sha256") == checksum:
                flags.append("duplicate_document_checksum")
                break
    if scan.credential_id and expected_identifier:
        from registry.models import PractitionerCredential
        if PractitionerCredential.objects.filter(identifier__iexact=expected_identifier).exclude(pk=scan.credential_id).exists():
            flags.append("duplicate_credential_identifier")
        if scan.credential.expires_on and scan.credential.expires_on < timezone.localdate():
            flags.append("credential_expired")
    if scan.organization_id and expected_identifier:
        from registry.models import Organization
        if Organization.objects.filter(license_number__iexact=expected_identifier).exclude(pk=scan.organization_id).exists():
            flags.append("duplicate_organization_license")
        if scan.organization.license_expires_on and scan.organization.license_expires_on < timezone.localdate():
            flags.append("organization_license_expired")
    if match_score is not None and match_score < 70:
        flags.append("credential_mismatch")
    lookup = regulator_lookup(scan, expected_identifier, issuer) if expected_identifier else {"status": "missing_identifier"}
    if lookup.get("status") in {"not_found", "revoked", "expired", "suspended"}:
        flags.append(f"regulator_{lookup.get('status')}")
    fraud_score = min(100, len(flags) * 25)
    recommendation = "manual_review"
    if not flags and (match_score is None or match_score >= 90) and lookup.get("status") in {"valid", "verified", "active"}:
        recommendation = "approve"
    elif fraud_score >= 75:
        recommendation = "reject"
    scan.status = "completed"
    scan.extracted_fields = {**fields, "quality_metadata": quality_meta, "document_checksum_sha256": checksum, "expected_name": expected_name, "expected_identifier": expected_identifier}
    scan.document_quality_score = quality
    scan.match_score = match_score
    scan.fraud_score = fraud_score
    scan.flags = flags
    scan.regulator_response = lookup
    scan.recommendation = recommendation
    scan.completed_at = timezone.now()
    scan.save()
    return scan


# ---------------------------------------------------------------------------
# Event delivery
# ---------------------------------------------------------------------------
def sign_payload(secret, payload):
    return hmac.new(secret.encode(), json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(), hashlib.sha256).hexdigest()


def deliver_event_delivery(delivery):
    endpoint = delivery.endpoint
    payload = {
        "id": str(delivery.event.event_id),
        "event_type": delivery.event.event_type,
        "occurred_at": delivery.event.occurred_at.isoformat(),
        "payload": delivery.event.payload,
        "schema": {"name": delivery.schema.name, "version": delivery.schema.version} if delivery.schema_id else None,
    }
    headers = {"Idempotency-Key": delivery.idempotency_key}
    secret = os.getenv(endpoint.credentials_reference, "") if endpoint.credentials_reference else ""
    if secret:
        headers["X-MyDoctor-Signature"] = sign_payload(secret, payload)
    try:
        if delivery.schema_id:
            try:
                from jsonschema import validate as validate_json_schema
                validate_json_schema(instance=payload.get("payload", {}), schema=delivery.schema.json_schema or {})
            except ImportError as exc:
                raise EnterpriseServiceError("jsonschema is required for versioned event delivery.") from exc
            except Exception as exc:
                raise EnterpriseServiceError(f"Event payload does not satisfy {delivery.schema.name} v{delivery.schema.version}: {exc}") from exc

        if endpoint.endpoint_type in {"webhook", "fhir", "warehouse"}:
            if not endpoint.base_url:
                raise EnterpriseServiceError(f"{endpoint.endpoint_type} endpoint URL is not configured.")
            code, response = http_json(endpoint.base_url, method="POST", data=payload, headers=headers)
        elif endpoint.endpoint_type == "kafka":
            proxy = endpoint.base_url or os.getenv("KAFKA_REST_PROXY_URL", "")
            if proxy:
                code, response = http_json(
                    f"{proxy.rstrip('/')}/topics/{endpoint.topic}", method="POST",
                    data={"records": [{"key": delivery.idempotency_key, "value": payload}]}, headers=headers,
                )
            else:
                bootstrap = (endpoint.configuration or {}).get("bootstrap_servers") or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
                if not bootstrap or not endpoint.topic:
                    raise EnterpriseServiceError("Kafka bootstrap servers and topic are required.")
                try:
                    from kafka import KafkaProducer
                    producer = KafkaProducer(
                        bootstrap_servers=[item.strip() for item in bootstrap.split(",") if item.strip()],
                        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                        key_serializer=lambda value: str(value).encode("utf-8"),
                        acks="all", retries=5,
                        security_protocol=(endpoint.configuration or {}).get("security_protocol", "PLAINTEXT"),
                    )
                    metadata = producer.send(endpoint.topic, key=delivery.idempotency_key, value=payload).get(timeout=20)
                    producer.flush(timeout=10)
                    producer.close(timeout=10)
                    code, response = 200, {"topic": metadata.topic, "partition": metadata.partition, "offset": metadata.offset}
                except Exception as exc:
                    raise EnterpriseServiceError(f"Kafka publish failed: {exc}") from exc
        elif endpoint.endpoint_type == "rabbitmq":
            bridge = endpoint.base_url or os.getenv("RABBITMQ_PUBLISH_BRIDGE_URL", "")
            if bridge and bridge.startswith(("http://", "https://")):
                code, response = http_json(bridge, method="POST", data={"routing_key": endpoint.topic, "payload": payload}, headers=headers)
            else:
                broker_url = bridge or os.getenv("RABBITMQ_URL", "")
                if not broker_url:
                    raise EnterpriseServiceError("RabbitMQ URL or publish bridge is not configured.")
                try:
                    import pika
                    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
                    channel = connection.channel()
                    exchange = (endpoint.configuration or {}).get("exchange", "")
                    if exchange:
                        channel.exchange_declare(exchange=exchange, exchange_type=(endpoint.configuration or {}).get("exchange_type", "topic"), durable=True)
                    channel.basic_publish(
                        exchange=exchange,
                        routing_key=endpoint.topic,
                        body=json.dumps(payload).encode("utf-8"),
                        properties=pika.BasicProperties(
                            content_type="application/json", delivery_mode=2,
                            message_id=delivery.idempotency_key,
                            headers={"schema": delivery.schema.name if delivery.schema_id else "", "schema_version": delivery.schema.version if delivery.schema_id else None},
                        ),
                        mandatory=False,
                    )
                    connection.close()
                    code, response = 200, {"routing_key": endpoint.topic, "published": True}
                except Exception as exc:
                    raise EnterpriseServiceError(f"RabbitMQ publish failed: {exc}") from exc
        elif endpoint.endpoint_type == "sftp":
            if not endpoint.base_url:
                raise EnterpriseServiceError("SFTP endpoint URL is not configured.")
            try:
                import paramiko
                parsed = urllib.parse.urlparse(endpoint.base_url)
                configuration = endpoint.configuration or {}
                username = parsed.username or configuration.get("username", "")
                password = secret or configuration.get("password", "")
                private_key_path = configuration.get("private_key_path", "")
                transport = paramiko.Transport((parsed.hostname, parsed.port or 22))
                if private_key_path:
                    key = paramiko.RSAKey.from_private_key_file(private_key_path, password=configuration.get("private_key_passphrase"))
                    transport.connect(username=username, pkey=key)
                else:
                    transport.connect(username=username, password=password)
                client = paramiko.SFTPClient.from_transport(transport)
                directory = parsed.path.rstrip("/") or "/"
                filename = f"{delivery.event.event_type}-{delivery.event.event_id}.json"
                with client.open(f"{directory}/{filename}", "w") as handle:
                    handle.write(json.dumps(payload))
                client.close(); transport.close()
                code, response = 200, {"path": f"{directory}/{filename}", "uploaded": True}
            except Exception as exc:
                raise EnterpriseServiceError(f"SFTP delivery failed: {exc}") from exc
        else:
            raise EnterpriseServiceError(f"Unsupported endpoint type: {endpoint.endpoint_type}")
        delivery.status = "delivered"
        delivery.delivered_at = timezone.now()
        delivery.response_code = code
        delivery.response_body = json.dumps(response)[:5000]
        delivery.attempt_count += 1
        delivery.save()
        return True
    except Exception as exc:
        delivery.attempt_count += 1
        delivery.response_body = str(exc)[:5000]
        if delivery.attempt_count >= int(os.getenv("EVENT_DELIVERY_MAX_ATTEMPTS", "8")):
            delivery.status = "dead_letter"
            DeadLetterEvent.objects.get_or_create(delivery=delivery, defaults={"reason": str(exc), "payload_snapshot": payload})
        else:
            delivery.status = "retry"
            delay = min(3600, 30 * (2 ** min(delivery.attempt_count, 7)))
            delivery.next_attempt_at = timezone.now() + timedelta(seconds=delay)
        delivery.save()
        return False


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def execute_report(run):
    run.status = "running"
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    try:
        definition = run.report.definition or {}
        domain = definition.get("domain") or run.report.domain
        queryset = EnterpriseRecord.objects.all()
        if run.report.organization_id:
            queryset = queryset.filter(organization=run.report.organization)
        if domain and domain != "all":
            queryset = queryset.filter(domain=domain)
        filters = {key: value for key, value in (run.parameters or {}).items() if key in {"status", "record_type", "priority", "patient_id", "assigned_to_id"}}
        queryset = queryset.filter(**filters)
        by_status = list(queryset.values("status").annotate(total=Count("id")).order_by("status"))
        by_type = list(queryset.values("record_type").annotate(total=Count("id")).order_by("record_type"))
        rows = list(queryset.values("reference", "record_type", "status", "priority", "title", "occurred_at")[:10000])
        result = {"total": queryset.count(), "by_status": by_status, "by_type": by_type, "generated_at": timezone.now().isoformat()}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["reference", "record_type", "status", "priority", "title", "occurred_at"])
        writer.writeheader()
        for row in rows:
            row["occurred_at"] = row["occurred_at"].isoformat() if row["occurred_at"] else ""
            writer.writerow(row)
        run.output_file.save(f"report-{run.id}.csv", ContentFile(output.getvalue().encode("utf-8")), save=False)
        run.result = result
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save()
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error", "completed_at"])
    return run


# ---------------------------------------------------------------------------
# FHIR persistence helpers
# ---------------------------------------------------------------------------
def upsert_fhir_resource(resource_type, data, *, patient=None, organization=None, source_model="", source_id="", logical_id=None):
    logical_id = logical_id or data.get("id")
    if logical_id:
        try:
            logical_id = __import__("uuid").UUID(str(logical_id))
        except Exception:
            logical_id = None
    existing = FHIRResource.objects.filter(resource_type=resource_type, logical_id=logical_id).order_by("-version_id").first() if logical_id else None
    version = (existing.version_id + 1) if existing else 1
    return FHIRResource.objects.create(
        resource_type=resource_type,
        logical_id=logical_id or __import__("uuid").uuid4(),
        version_id=version,
        patient=patient,
        organization=organization,
        source_model=source_model,
        source_id=str(source_id or ""),
        data={**data, "resourceType": resource_type},
    )


def fhir_bundle(queryset):
    entries = [{"fullUrl": f"urn:uuid:{row.logical_id}", "resource": row.data} for row in queryset]
    return {"resourceType": "Bundle", "type": "searchset", "total": len(entries), "entry": entries}


# ---------------------------------------------------------------------------
# Clinical decision support, PACS, fleet, records, provider health and metrics
# ---------------------------------------------------------------------------
def medication_safety_check(medicine_ids, *, allergy_terms=None, condition_terms=None, pregnant=False, renal_impairment=False, hepatic_impairment=False):
    medicine_ids = [int(value) for value in medicine_ids or [] if str(value).isdigit()]
    medicines = list(MedicationKnowledge.objects.filter(id__in=medicine_ids, active=True))
    warnings = []
    interactions = MedicationInteraction.objects.filter(active=True).filter(
        Q(medicine_a_id__in=medicine_ids, medicine_b_id__in=medicine_ids)
    ).select_related("medicine_a", "medicine_b")
    for row in interactions:
        warnings.append({
            "type": "interaction",
            "severity": row.severity,
            "title": f"{row.medicine_a.generic_name} + {row.medicine_b.generic_name}",
            "clinical_effect": row.clinical_effect,
            "management": row.management,
            "evidence": row.evidence,
        })
    allergies = {str(value).strip().lower() for value in (allergy_terms or []) if str(value).strip()}
    conditions = {str(value).strip().lower() for value in (condition_terms or []) if str(value).strip()}
    for medicine in medicines:
        searchable_names = {medicine.generic_name.lower(), *[str(name).lower() for name in medicine.brand_names or []]}
        matched_allergies = sorted(allergies.intersection(searchable_names))
        if matched_allergies:
            warnings.append({"type": "allergy", "severity": "contraindicated", "title": f"Allergy alert: {medicine.generic_name}", "detail": matched_allergies})
        for contraindication in medicine.contraindications or []:
            if any(term in str(contraindication).lower() or str(contraindication).lower() in term for term in conditions):
                warnings.append({"type": "contraindication", "severity": "major", "title": medicine.generic_name, "detail": contraindication})
        if pregnant and medicine.pregnancy_category:
            severity = "major" if "contra" in medicine.pregnancy_category.lower() else "moderate"
            warnings.append({"type": "pregnancy", "severity": severity, "title": medicine.generic_name, "detail": medicine.pregnancy_category})
        if renal_impairment and medicine.renal_guidance:
            warnings.append({"type": "renal", "severity": "moderate", "title": medicine.generic_name, "detail": medicine.renal_guidance})
        if hepatic_impairment and medicine.hepatic_guidance:
            warnings.append({"type": "hepatic", "severity": "moderate", "title": medicine.generic_name, "detail": medicine.hepatic_guidance})
    severity_order = {"contraindicated": 4, "major": 3, "moderate": 2, "minor": 1}
    highest = max((severity_order.get(item.get("severity"), 0) for item in warnings), default=0)
    return {
        "medicines": [{"id": item.id, "generic_name": item.generic_name, "brand_names": item.brand_names} for item in medicines],
        "warnings": sorted(warnings, key=lambda item: severity_order.get(item.get("severity"), 0), reverse=True),
        "safe_to_continue": highest < 3,
        "requires_pharmacist_review": highest >= 2,
        "requires_prescriber_override": highest >= 3,
    }


def pacs_health_check(node):
    checked_at = timezone.now()
    tcp_ok = False
    dicomweb_ok = False
    errors = []
    started = timezone.now()
    try:
        with socket.create_connection((node.host, node.port), timeout=int(os.getenv("PACS_ECHO_TIMEOUT_SECONDS", "5"))):
            tcp_ok = True
    except Exception as exc:
        errors.append(f"DICOM TCP: {exc}")
    if node.dicomweb_base_url:
        try:
            request = urllib.request.Request(node.dicomweb_base_url.rstrip("/") + "/studies?limit=1", method="GET", headers={"Accept": "application/dicom+json"})
            with urllib.request.urlopen(request, timeout=int(os.getenv("PACS_ECHO_TIMEOUT_SECONDS", "5"))) as response:
                dicomweb_ok = 200 <= response.status < 500
        except Exception as exc:
            errors.append(f"DICOMweb: {exc}")
    ok = tcp_ok or dicomweb_ok
    node.last_echo_at = checked_at
    node.last_echo_ok = ok
    node.save(update_fields=["last_echo_at", "last_echo_ok"])
    return {"ok": ok, "tcp_ok": tcp_ok, "dicomweb_ok": dicomweb_ok, "errors": errors, "checked_at": checked_at, "latency_ms": int((timezone.now() - started).total_seconds() * 1000)}


def _distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0088
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_ambulances(latitude, longitude, organization=None, limit=10):
    vehicles = AmbulanceVehicle.objects.filter(active=True).exclude(status__in=["maintenance", "inactive"]).prefetch_related("crew")
    if organization:
        vehicles = vehicles.filter(organization=organization)
    results = []
    for vehicle in vehicles:
        telemetry = vehicle.telemetry.order_by("-recorded_at").first()
        if not telemetry:
            continue
        distance = _distance_km(latitude, longitude, telemetry.latitude, telemetry.longitude)
        eta_minutes = max(1, round(distance / max(float(telemetry.speed_kph or 30), 15) * 60))
        results.append({
            "vehicle_id": vehicle.id, "call_sign": vehicle.call_sign, "registration_number": vehicle.registration_number,
            "vehicle_type": vehicle.vehicle_type, "status": vehicle.status, "distance_km": round(distance, 2),
            "estimated_arrival_minutes": eta_minutes, "latitude": telemetry.latitude, "longitude": telemetry.longitude,
            "recorded_at": telemetry.recorded_at, "crew": [{"id": user.id, "name": user.display_name, "role": active_role(user)} for user in vehicle.crew.all()],
        })
    return sorted(results, key=lambda row: row["distance_km"])[:max(1, min(int(limit), 50))]


@transaction.atomic
def scan_duplicate_patients(min_score=70):
    rows = list(MasterPatientIndex.objects.filter(status="active").select_related("patient").order_by("id"))
    created = 0
    updated = 0
    candidates = []
    for index, left in enumerate(rows):
        for right in rows[index + 1:]:
            matching = []
            scores = []
            name_score = _text_similarity(left.normalized_name, right.normalized_name)
            if name_score >= 70:
                matching.append("name")
                scores.append(name_score)
            if left.normalized_phone and left.normalized_phone == right.normalized_phone:
                matching.append("phone")
                scores.append(100)
            if left.national_identifier and left.national_identifier == right.national_identifier:
                matching.append("national_identifier")
                scores.append(100)
            if left.date_of_birth and left.date_of_birth == right.date_of_birth:
                matching.append("date_of_birth")
                scores.append(100)
            left_ids = {str(item.get("value", "")).lower() for item in left.identifiers or [] if isinstance(item, dict)}
            right_ids = {str(item.get("value", "")).lower() for item in right.identifiers or [] if isinstance(item, dict)}
            if (left_ids & right_ids) - {""}:
                matching.append("identifier")
                scores.append(100)
            if not scores:
                continue
            score = round(sum(scores) / len(scores), 2)
            if score < float(min_score):
                continue
            candidate, was_created = DuplicatePatientCandidate.objects.update_or_create(
                patient_a=left, patient_b=right,
                defaults={"score": score, "matching_fields": matching, "status": "pending", "notes": "Generated by enterprise MPI duplicate scan."},
            )
            created += int(was_created)
            updated += int(not was_created)
            candidates.append(candidate)
    return {"created": created, "updated": updated, "total_candidates": len(candidates)}


def provider_health_check(provider):
    configuration = provider.configuration or {}
    errors = []
    ok = False
    if provider.provider_type in {"smtp", "django_email"} or provider.channel == "email":
        host = configuration.get("host") or os.getenv("EMAIL_HOST", "")
        port = int(configuration.get("port") or os.getenv("EMAIL_PORT", "587"))
        if host:
            try:
                with socket.create_connection((host, port), timeout=5):
                    ok = True
            except Exception as exc:
                errors.append(str(exc))
        else:
            errors.append("Email host is not configured.")
    else:
        url = configuration.get("health_url") or configuration.get("url") or configuration.get("endpoint")
        token = os.getenv(provider.credentials_reference, "") if provider.credentials_reference else ""
        if url:
            try:
                request = urllib.request.Request(url, method="GET", headers={"Authorization": f"Bearer {token}"} if token else {})
                with urllib.request.urlopen(request, timeout=5) as response:
                    ok = 200 <= response.status < 500
            except Exception as exc:
                errors.append(str(exc))
        else:
            errors.append("Provider endpoint is not configured.")
    provider.health_status = "healthy" if ok else "unhealthy"
    provider.last_health_check_at = timezone.now()
    provider.save(update_fields=["health_status", "last_health_check_at"])
    return {"ok": ok, "provider": provider.name, "channel": provider.channel, "health_status": provider.health_status, "errors": errors, "checked_at": provider.last_health_check_at}


def fhir_bundle_for_patient(patient, organization=None):
    resources = FHIRResource.objects.filter(patient=patient, status="active").order_by("resource_type", "logical_id", "-version_id")
    if organization:
        resources = resources.filter(Q(organization=organization) | Q(organization__isnull=True))
    latest = {}
    for resource in resources:
        latest.setdefault((resource.resource_type, resource.logical_id), resource)
    entries = []
    for resource in latest.values():
        data = dict(resource.data or {})
        data.setdefault("resourceType", resource.resource_type)
        data.setdefault("id", str(resource.logical_id))
        entries.append({"fullUrl": f"urn:uuid:{resource.logical_id}", "resource": data})
    return {
        "resourceType": "Bundle", "type": "collection", "timestamp": timezone.now().isoformat(),
        "total": len(entries), "entry": entries,
        "meta": {"tag": [{"system": "urn:mydoctor:bundle", "code": "patient-export"}]},
    }


def platform_metrics():
    from django.contrib.auth import get_user_model
    from registry.models import Organization
    from interoperability.models import OutboxEvent
    User = get_user_model()
    return {
        "users_total": User.objects.count(),
        "users_active": User.objects.filter(is_active=True).count(),
        "organizations_total": Organization.objects.count(),
        "enterprise_records_total": EnterpriseRecord.objects.count(),
        "enterprise_records_open": EnterpriseRecord.objects.exclude(status__in=["completed", "cancelled", "closed", "resolved"]).count(),
        "event_deliveries_pending": EventDelivery.objects.filter(status__in=["pending", "retry"]).count(),
        "event_deliveries_dead_letter": EventDelivery.objects.filter(status="dead_letter").count(),
        "outbox_pending": OutboxEvent.objects.filter(published_at__isnull=True).count(),
        "verification_pending": VerificationAutomation.objects.filter(status__in=["queued", "processing"]).count(),
        "security_high_open": SecurityOperation.objects.filter(severity__in=["high", "critical"]).exclude(status__in=["completed", "closed", "approved"]).count(),
        "notification_providers_unhealthy": NotificationProvider.objects.exclude(health_status="healthy").count(),
    }
