#!/usr/bin/env python3
"""Dependency-light proof that every deep page has an explicit operating mode."""
from pathlib import Path
import ast
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from journeys.definitions import MANIFEST, definition_for

errors = []
stats = {"total": 0, "actionable": 0, "read_only": 0, "adapters": {}, "modes": {}, "sources": {}}
operational_adapters = {"operational_action", "front_desk_operation", "facility_operation", "insurance_operation", "radiology_operation"}
for slug in sorted(MANIFEST):
    definition = definition_for(slug)
    stats["total"] += 1
    mode = definition.get("page_mode")
    source = definition.get("canonical_source")
    adapter = definition.get("adapter")
    stats["modes"][mode] = stats["modes"].get(mode, 0) + 1
    stats["sources"][source] = stats["sources"].get(source, 0) + 1
    stats["adapters"][str(adapter)] = stats["adapters"].get(str(adapter), 0) + 1
    if definition.get("create_allowed", True):
        stats["actionable"] += 1
        if not adapter:
            errors.append(f"{slug}: actionable page has no canonical adapter")
        if source in {None, "page_data", "workflow_queue"}:
            errors.append(f"{slug}: actionable page has non-transactional source {source!r}")
    else:
        stats["read_only"] += 1
        if mode not in {"dashboard", "detail", "work_queue", "reference"}:
            errors.append(f"{slug}: read-only page has invalid mode {mode!r}")

page_data = (ROOT / "backend/journeys/page_data.py").read_text()
if '"configured": False' in page_data or '"kind": "workflow_only"' in page_data:
    errors.append("page_data.py still exposes an unconfigured/workflow_only fallback")
services = (ROOT / "backend/journeys/services.py").read_text()
for token in ["OperationalAction", "_sync_operational_action", "_execute_operational_effect", "perform_action"]:
    if token not in services:
        errors.append(f"journey services missing {token}")
handled_adapters = set(__import__("re").findall(r'adapter == "([a-z0-9_]+)"', services)) | operational_adapters | {"enterprise_record", "operational_action"}
actionable_adapters = {definition_for(slug).get("adapter") for slug in MANIFEST if definition_for(slug).get("create_allowed", True)}
missing_handlers = sorted(adapter for adapter in actionable_adapters if adapter and adapter not in handled_adapters)
if missing_handlers:
    errors.append("actionable adapters without create/action service handling: " + ", ".join(missing_handlers))

if errors:
    print("Workflow completion audit failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)
print(json.dumps(stats, indent=2, sort_keys=True))
print("Workflow completion audit passed: every actionable page is adapter-backed and every other page is explicitly classified")
