#!/usr/bin/env python3
"""Reject request-time authorization code that bypasses the active role context."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1] / "backend"
SCAN_NAMES = {"views.py", "services.py", "consumers.py", "permissions.py", "page_data.py", "admin_views.py"}
violations = []
for path in ROOT.rglob("*.py"):
    if "migrations" in path.parts or path.name not in SCAN_NAMES:
        continue
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), 1):
        if re.search(r"\brequest\.user\.role\b", line):
            violations.append((path, line_no, line.strip()))
        if path.name in {"views.py", "consumers.py"} and re.search(r"\buser\.role\s*(==|!=|\bin\b|\bnot in\b)", line):
            # Target-user serialization and registration branches are allowed only
            # when the line is explicitly not about request.user.
            if "request.user" not in line and any(token in str(path) for token in ("accounts/views.py", "workforce/views.py")):
                continue
            violations.append((path, line_no, line.strip()))

if violations:
    print("Unsafe direct role authorization checks found:")
    for path, line_no, line in violations:
        print(f"- {path.relative_to(ROOT.parent)}:{line_no}: {line}")
    sys.exit(1)

required = {
    ROOT / "accounts" / "permissions.py": ["active_role", "role_allowed"],
    ROOT / "clinical" / "services.py": ["active_privileged_access", "patient-specific elevation"],
    ROOT / "enterprise" / "access.py": ["active_context_for", "can_manage_platform"],
}
for path, tokens in required.items():
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            print(f"Missing authorization control {token!r} in {path}")
            sys.exit(1)
print("Authorization audit: active-role and controlled-clinical-access checks passed")
