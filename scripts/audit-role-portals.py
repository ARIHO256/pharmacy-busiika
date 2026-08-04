#!/usr/bin/env python3
"""Dependency-free role, route, schema and demo-account consistency audit."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def extract_user_roles() -> set[str]:
    source = text("backend/accounts/models.py")
    block = source.split("class Role(models.TextChoices):", 1)[1].split("username = None", 1)[0]
    return set(re.findall(r'^\s+[A-Z][A-Z0-9_]*\s*=\s*"([a-z0-9_]+)"', block, re.M))


def extract_role_home() -> dict[str, str]:
    source = text("frontend/src/auth/AuthContext.jsx")
    block = source.split("export const ROLE_HOME = {", 1)[1].split("}\n", 1)[0]
    return dict(re.findall(r"^\s*([a-z0-9_]+):\s*'([^']+)'", block, re.M))


def extract_enterprise_portals() -> dict[str, str]:
    source = text("frontend/src/portals/enterprise/roleCatalog.js")
    block = source.split("const ROLE_PORTALS = {", 1)[1].split("\n}\n\nexport function portalForRole", 1)[0]
    result: dict[str, str] = {}
    for match in re.finditer(r"^\s{2}([a-z0-9_]+):\s*\{", block, re.M):
        role = match.group(1)
        remainder = block[match.end():]
        path_match = re.search(r"\bpath:\s*'([^']+)'", remainder)
        if path_match:
            result[role] = "/" + path_match.group(1).lstrip("/")
    return result


def extract_static_portal_roles() -> set[str]:
    source = text("frontend/src/App.jsx")
    roles: set[str] = set()
    for match in re.finditer(r"Portal\(\{(.*?)\}\)", source, re.S):
        body = match.group(1)
        roles.update(re.findall(r"'([a-z][a-z0-9_]+)'", body))
    # Exclude words that are route/title fragments rather than role codes.
    return roles & extract_user_roles()


def schema_keys() -> set[str]:
    tree = ast.parse(text("backend/enterprise/schemas.py"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RECORD_SCHEMAS" for t in node.targets):
            if not isinstance(node.value, ast.Dict):
                fail("RECORD_SCHEMAS is no longer a literal dictionary")
            return {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
    fail("RECORD_SCHEMAS was not found")
    return set()


def scan_function_calls(source: str, function_names: set[str]):
    calls = []
    for name in function_names:
        needle = name + "("
        cursor = 0
        while True:
            start = source.find(needle, cursor)
            if start < 0:
                break
            i = start + len(name)
            depth = 0
            quote = None
            escaped = False
            while i < len(source):
                ch = source[i]
                if quote:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == quote:
                        quote = None
                else:
                    if ch in {"'", '"', "`"}:
                        quote = ch
                    elif ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            calls.append((name, source[start : i + 1]))
                            cursor = i + 1
                            break
                i += 1
            else:
                fail(f"Unbalanced JavaScript call beginning at {start}: {name}")
    return calls


def split_args(call: str) -> list[str]:
    body = call[call.find("(") + 1 : -1]
    args, buffer = [], []
    parens = brackets = braces = 0
    quote = None
    escaped = False
    for ch in body:
        if quote:
            buffer.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            buffer.append(ch)
        elif ch == "(":
            parens += 1; buffer.append(ch)
        elif ch == ")":
            parens -= 1; buffer.append(ch)
        elif ch == "[":
            brackets += 1; buffer.append(ch)
        elif ch == "]":
            brackets -= 1; buffer.append(ch)
        elif ch == "{":
            braces += 1; buffer.append(ch)
        elif ch == "}":
            braces -= 1; buffer.append(ch)
        elif ch == "," and not any((parens, brackets, braces)):
            args.append("".join(buffer).strip()); buffer = []
        else:
            buffer.append(ch)
    args.append("".join(buffer).strip())
    return args


def referenced_record_types() -> set[str]:
    result: set[str] = set()
    for path, function_names, arg_index in [
        ("frontend/src/portals/enterprise/roleCatalog.js", {"records"}, 4),
        ("frontend/src/portals/enterprise/coreModules.js", {"module"}, 4),
    ]:
        source = text(path)
        for name, call in scan_function_calls(source, function_names):
            args = split_args(call)
            if len(args) <= arg_index:
                continue
            result.update(re.findall(r"['\"]([a-z][a-z0-9_]+)['\"]", args[arg_index]))
    return result


def demo_account_roles() -> set[str]:
    tree = ast.parse(text("backend/seed.py"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEMO_ROLE_ACCOUNTS" for t in node.targets):
            if not isinstance(node.value, ast.Dict):
                fail("DEMO_ROLE_ACCOUNTS is no longer a literal dictionary")
            return {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
    fail("DEMO_ROLE_ACCOUNTS was not found in backend/seed.py")
    return set()


def main() -> None:
    roles = extract_user_roles()
    homes = extract_role_home()
    enterprise = extract_enterprise_portals()
    static = extract_static_portal_roles()

    missing_homes = sorted(roles - homes.keys())
    if missing_homes:
        fail(f"Roles missing ROLE_HOME entries: {', '.join(missing_homes)}")

    routed = static | enterprise.keys()
    missing_routes = sorted(roles - routed)
    if missing_routes:
        fail(f"Roles missing a static or enterprise portal: {', '.join(missing_routes)}")

    path_mismatches = sorted(
        f"{role}: ROLE_HOME={homes[role]} catalogue={path}"
        for role, path in enterprise.items()
        if homes.get(role) != path
    )
    if path_mismatches:
        fail("Enterprise portal path mismatches: " + "; ".join(path_mismatches))

    schemas = schema_keys()
    referenced = referenced_record_types()
    unknown = sorted(referenced - schemas)
    if unknown:
        fail(f"Frontend modules reference unknown workflow schemas: {', '.join(unknown)}")
    unreferenced = sorted(schemas - referenced)
    if unreferenced:
        fail(f"Backend workflow schemas missing from all role pages: {', '.join(unreferenced)}")

    seed_roles = demo_account_roles()
    missing_seed = sorted(roles - seed_roles)
    if missing_seed:
        fail(f"Roles missing a demonstrable seed account: {', '.join(sorted(set(missing_seed)))}")

    print(f"Role catalogue: {len(roles)} roles, {len(homes)} home routes, {len(routed)} routed roles")
    print(f"Workflow catalogue: {len(schemas)} backend schemas, {len(referenced)} referenced by role pages")
    print(f"Demo coverage: {len(seed_roles)} explicitly seeded role codes")
    print("Role, portal, workflow and demo-account audit passed.")


if __name__ == "__main__":
    main()
