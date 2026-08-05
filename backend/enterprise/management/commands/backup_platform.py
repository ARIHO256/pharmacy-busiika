"""Create an auditable compressed database backup.

PostgreSQL deployments use pg_dump. SQLite demonstrations are copied safely.
The resulting archive is saved through Django's default storage, which means it
inherits private S3/MinIO controls in production.
"""
import gzip
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from enterprise.models import SecurityOperation


class Command(BaseCommand):
    help = "Create a compressed database backup in private object storage and record evidence."

    def add_arguments(self, parser):
        parser.add_argument("--prefix", default="database-backups")

    def handle(self, *args, **options):
        operation = SecurityOperation.objects.create(
            operation_type="backup",
            status="running",
            severity="high",
            title="Database backup",
            description="Automated database backup initiated by management command.",
            started_at=timezone.now(),
            scope={"database_engine": settings.DATABASES["default"]["ENGINE"]},
        )
        try:
            with tempfile.TemporaryDirectory(prefix="healthpilot-backup-") as temp_dir:
                temp = Path(temp_dir)
                raw = temp / "database.dump"
                db = settings.DATABASES["default"]
                if db["ENGINE"].endswith("sqlite3"):
                    source = Path(db["NAME"])
                    if not source.exists():
                        raise CommandError(f"SQLite database does not exist: {source}")
                    shutil.copy2(source, raw)
                else:
                    env = os.environ.copy()
                    env["PGPASSWORD"] = db.get("PASSWORD", "")
                    command = [
                        "pg_dump", "--format=custom", "--no-owner", "--no-acl",
                        "--host", str(db.get("HOST") or "localhost"),
                        "--port", str(db.get("PORT") or 5432),
                        "--username", str(db.get("USER") or ""),
                        "--file", str(raw), str(db.get("NAME") or ""),
                    ]
                    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
                compressed = temp / f"healthpilot-{timezone.now():%Y%m%dT%H%M%SZ}.dump.gz"
                with raw.open("rb") as source, gzip.open(compressed, "wb", compresslevel=9) as target:
                    shutil.copyfileobj(source, target)
                digest = hashlib.sha256(compressed.read_bytes()).hexdigest()
                destination = f"{options['prefix'].strip('/')}/{compressed.name}"
                with compressed.open("rb") as handle:
                    stored_name = default_storage.save(destination, File(handle))
                operation.status = "completed"
                operation.completed_at = timezone.now()
                operation.evidence = {
                    "storage_name": stored_name,
                    "sha256": digest,
                    "compressed_bytes": compressed.stat().st_size,
                }
                operation.save(update_fields=["status", "completed_at", "evidence"])
                self.stdout.write(self.style.SUCCESS(f"Backup saved as {stored_name}"))
                self.stdout.write(f"sha256={digest}")
        except Exception as exc:
            operation.status = "failed"
            operation.completed_at = timezone.now()
            operation.findings = [{"type": "backup_failure", "detail": str(exc)}]
            operation.save(update_fields=["status", "completed_at", "findings"])
            raise CommandError(str(exc)) from exc
