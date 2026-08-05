import gzip
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from enterprise.models import SecurityOperation


class Command(BaseCommand):
    help = "Download and integrity-check a backup; PostgreSQL custom dumps are checked with pg_restore --list."

    def add_arguments(self, parser):
        parser.add_argument("storage_name")
        parser.add_argument("--sha256", default="")

    def handle(self, *args, **options):
        operation = SecurityOperation.objects.create(
            operation_type="restore_test",
            status="running",
            severity="high",
            title="Backup verification and restore-list test",
            started_at=timezone.now(),
            scope={"storage_name": options["storage_name"]},
        )
        try:
            with tempfile.TemporaryDirectory(prefix="healthpilot-restore-test-") as temp_dir:
                compressed = Path(temp_dir) / "backup.dump.gz"
                with default_storage.open(options["storage_name"], "rb") as source, compressed.open("wb") as target:
                    shutil.copyfileobj(source, target)
                digest = hashlib.sha256(compressed.read_bytes()).hexdigest()
                if options["sha256"] and digest.lower() != options["sha256"].lower():
                    raise CommandError("Backup checksum mismatch")
                raw = Path(temp_dir) / "backup.dump"
                with gzip.open(compressed, "rb") as source, raw.open("wb") as target:
                    shutil.copyfileobj(source, target)
                details = {"sha256": digest, "uncompressed_bytes": raw.stat().st_size}
                if raw.read_bytes()[:15].startswith(b"PGDMP"):
                    subprocess.run(["pg_restore", "--list", str(raw)], check=True, capture_output=True, text=True)
                    details["pg_restore_list"] = "passed"
                else:
                    details["format"] = "sqlite_or_plain_dump"
                operation.status = "completed"
                operation.completed_at = timezone.now()
                operation.evidence = details
                operation.save(update_fields=["status", "completed_at", "evidence"])
                self.stdout.write(self.style.SUCCESS(f"Backup verification passed: {details}"))
        except Exception as exc:
            operation.status = "failed"
            operation.completed_at = timezone.now()
            operation.findings = [{"type": "restore_test_failure", "detail": str(exc)}]
            operation.save(update_fields=["status", "completed_at", "findings"])
            raise CommandError(str(exc)) from exc
