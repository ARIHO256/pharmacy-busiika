"""Central upload validation and optional ClamAV scanning.

The application never trusts a browser supplied MIME type.  Every accepted upload is
checked for size, extension, a small set of file signatures, and (when enabled)
streamed to ClamAV before it is persisted.
"""
from __future__ import annotations

import hashlib
import os
import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class UploadPolicy:
    label: str
    max_bytes: int
    extensions: frozenset[str]
    mime_types: frozenset[str]


IMAGE_POLICY = UploadPolicy(
    label="image",
    max_bytes=8 * 1024 * 1024,
    extensions=frozenset({".jpg", ".jpeg", ".png", ".webp"}),
    mime_types=frozenset({"image/jpeg", "image/png", "image/webp"}),
)

CREDENTIAL_POLICY = UploadPolicy(
    label="credential document",
    max_bytes=10 * 1024 * 1024,
    extensions=frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf"}),
    mime_types=frozenset({"image/jpeg", "image/png", "image/webp", "application/pdf"}),
)

CLINICAL_DOCUMENT_POLICY = UploadPolicy(
    label="clinical document",
    max_bytes=20 * 1024 * 1024,
    extensions=frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf", ".csv", ".txt"}),
    mime_types=frozenset(
        {
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
            "text/csv",
            "text/plain",
            "application/vnd.ms-excel",
        }
    ),
)

CHAT_ATTACHMENT_POLICY = UploadPolicy(
    label="message attachment",
    max_bytes=12 * 1024 * 1024,
    extensions=frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf", ".txt"}),
    mime_types=frozenset(
        {"image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain"}
    ),
)

REPORT_POLICY = UploadPolicy(
    label="report output",
    max_bytes=30 * 1024 * 1024,
    extensions=frozenset({".pdf", ".csv", ".xlsx", ".json"}),
    mime_types=frozenset(
        {
            "application/pdf",
            "text/csv",
            "application/json",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
    ),
)

_BLOCKED_EXTENSIONS = frozenset(
    {
        ".exe",
        ".com",
        ".bat",
        ".cmd",
        ".ps1",
        ".sh",
        ".js",
        ".mjs",
        ".jar",
        ".apk",
        ".dll",
        ".so",
        ".php",
        ".py",
        ".rb",
        ".pl",
        ".html",
        ".htm",
        ".svg",
    }
)


def _read_head(upload, size: int = 8192) -> bytes:
    try:
        position = upload.tell()
    except (AttributeError, OSError):
        position = None
    try:
        upload.seek(0)
        return upload.read(size)
    finally:
        try:
            upload.seek(position or 0)
        except (AttributeError, OSError):
            pass


def _iter_chunks(upload, chunk_size: int = 64 * 1024) -> Iterable[bytes]:
    try:
        position = upload.tell()
    except (AttributeError, OSError):
        position = None
    try:
        upload.seek(0)
        if hasattr(upload, "chunks"):
            yield from upload.chunks(chunk_size=chunk_size)
        else:
            while True:
                chunk = upload.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        try:
            upload.seek(position or 0)
        except (AttributeError, OSError):
            pass


def _looks_like(extension: str, head: bytes) -> bool:
    if extension in {".jpg", ".jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if extension == ".pdf":
        return head.lstrip().startswith(b"%PDF-")
    if extension == ".xlsx":
        return head.startswith(b"PK\x03\x04")
    if extension in {".csv", ".txt", ".json"}:
        # Reject binary control bytes except tab/newline/carriage return.
        return not any(byte < 9 or (13 < byte < 32) for byte in head)
    return False


def _clamav_scan(upload) -> None:
    enabled = bool(getattr(settings, "CLAMAV_ENABLED", False))
    required = bool(getattr(settings, "CLAMAV_REQUIRED", False))
    if not enabled and not required:
        return

    host = getattr(settings, "CLAMAV_HOST", "clamav")
    port = int(getattr(settings, "CLAMAV_PORT", 3310))
    timeout = float(getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 12))
    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            client.sendall(b"zINSTREAM\0")
            for chunk in _iter_chunks(upload):
                if chunk:
                    client.sendall(struct.pack("!I", len(chunk)))
                    client.sendall(chunk)
            client.sendall(struct.pack("!I", 0))
            response = client.recv(4096).decode("utf-8", errors="replace").strip("\0\r\n")
    except OSError as exc:
        if required:
            raise ValidationError(
                "The security scanner is temporarily unavailable. Please try the upload again."
            ) from exc
        return

    if "FOUND" in response.upper():
        raise ValidationError("The uploaded file failed the malware safety scan.")
    if "OK" not in response.upper() and required:
        raise ValidationError("The uploaded file could not be verified by the security scanner.")


def validate_upload(upload, policy: UploadPolicy):
    if upload in (None, ""):
        return upload

    name = os.path.basename(str(getattr(upload, "name", "upload")))
    extension = Path(name).suffix.lower()
    size = int(getattr(upload, "size", 0) or 0)
    content_type = str(getattr(upload, "content_type", "") or "").lower()

    if not extension or extension in _BLOCKED_EXTENSIONS:
        raise ValidationError(f"Unsupported {policy.label} file type.")
    if extension not in policy.extensions:
        allowed = ", ".join(sorted(ext.lstrip(".").upper() for ext in policy.extensions))
        raise ValidationError(f"{policy.label.title()} must be one of: {allowed}.")
    if size <= 0:
        raise ValidationError("The uploaded file is empty.")
    if size > policy.max_bytes:
        limit_mb = policy.max_bytes // (1024 * 1024)
        raise ValidationError(f"{policy.label.title()} cannot exceed {limit_mb} MB.")
    if content_type and content_type not in policy.mime_types:
        raise ValidationError(f"The browser reported an unsupported {policy.label} content type.")

    head = _read_head(upload)
    if not _looks_like(extension, head):
        raise ValidationError(
            "The file contents do not match the selected file extension."
        )

    _clamav_scan(upload)
    return upload


def upload_sha256(upload) -> str:
    digest = hashlib.sha256()
    for chunk in _iter_chunks(upload):
        digest.update(chunk)
    return digest.hexdigest()


def validate_image_upload(upload):
    return validate_upload(upload, IMAGE_POLICY)


def validate_credential_upload(upload):
    return validate_upload(upload, CREDENTIAL_POLICY)


def validate_clinical_document_upload(upload):
    return validate_upload(upload, CLINICAL_DOCUMENT_POLICY)


def validate_chat_attachment(upload):
    return validate_upload(upload, CHAT_ATTACHMENT_POLICY)


def validate_report_output(upload):
    return validate_upload(upload, REPORT_POLICY)
