#!/usr/bin/env python3
"""Generate the enterprise app's initial migration without importing Django.

This repository is occasionally assembled in restricted build environments where
Django packages cannot be downloaded.  The generator transforms the declarative
model field AST into a normal versioned migration and is validated by the static
release gate.  In a connected environment, ``makemigrations --check`` remains the
final authority.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend/enterprise/models.py"
TARGET = ROOT / "backend/enterprise/migrations/0001_initial.py"


def is_model_class(node: ast.ClassDef) -> bool:
    return any(ast.unparse(base) == "models.Model" for base in node.bases)


def text_choices(node: ast.ClassDef) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for child in node.body:
        if not isinstance(child, ast.ClassDef):
            continue
        if not any(ast.unparse(base) == "models.TextChoices" for base in child.bases):
            continue
        for assignment in child.body:
            if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1:
                continue
            target = assignment.targets[0]
            if not isinstance(target, ast.Name):
                continue
            try:
                value = ast.literal_eval(assignment.value)
            except Exception:
                continue
            if isinstance(value, tuple) and len(value) == 2:
                result[f"{child.name}.{target.id}"] = (str(value[0]), str(value[1]))
    return result


class MigrationTransformer(ast.NodeTransformer):
    def __init__(self, model_name: str, model_names: set[str], choices: dict[str, tuple[str, str]]):
        self.model_name = model_name
        self.model_names = model_names
        self.choices = choices

    def visit_Call(self, node: ast.Call):
        node = self.generic_visit(node)
        function_name = ast.unparse(node.func)
        if function_name in {"models.ForeignKey", "models.OneToOneField", "models.ManyToManyField"} and node.args:
            target = node.args[0]
            if isinstance(target, ast.Name) and target.id in self.model_names:
                node.args[0] = ast.Constant(value=f"enterprise.{target.id.lower()}")
            elif isinstance(target, ast.Constant) and isinstance(target.value, str):
                if target.value == "self":
                    node.args[0] = ast.Constant(value=f"enterprise.{self.model_name.lower()}")
                elif "." in target.value:
                    app, model = target.value.split(".", 1)
                    node.args[0] = ast.Constant(value=f"{app}.{model.lower()}")
        return node

    def visit_Name(self, node: ast.Name):
        if node.id == "AUTH_USER":
            return ast.Attribute(value=ast.Name(id="settings", ctx=ast.Load()), attr="AUTH_USER_MODEL", ctx=ast.Load())
        if node.id == "generate_client_id":
            return ast.Attribute(
                value=ast.Attribute(value=ast.Name(id="enterprise", ctx=ast.Load()), attr="models", ctx=ast.Load()),
                attr="generate_client_id",
                ctx=ast.Load(),
            )
        return node

    def visit_Attribute(self, node: ast.Attribute):
        key = ast.unparse(node)
        if key.endswith(".choices"):
            prefix = key[: -len(".choices")]
            values = [
                ast.Tuple(elts=[ast.Constant(value=value), ast.Constant(value=label)], ctx=ast.Load())
                for name, (value, label) in self.choices.items()
                if name.startswith(prefix + ".")
            ]
            if values:
                return ast.List(elts=values, ctx=ast.Load())
        if key in self.choices:
            return ast.Constant(value=self.choices[key][0])
        return self.generic_visit(node)


def assignment_value(class_node: ast.ClassDef, name: str):
    for child in class_node.body:
        if isinstance(child, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in child.targets):
            return child.value
    return None


def migration_source() -> str:
    source_tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    models = [node for node in source_tree.body if isinstance(node, ast.ClassDef) and is_model_class(node)]
    model_names = {node.name for node in models}
    lines = [
        '"""Initial enterprise schema covering all 21 requested platform sections."""',
        "import uuid",
        "import django.db.models.deletion",
        "from django.utils import timezone",
        "import enterprise.models",
        "from django.conf import settings",
        "from django.db import migrations, models",
        "",
        "",
        "class Migration(migrations.Migration):",
        "    initial = True",
        "",
        "    dependencies = [",
        "        migrations.swappable_dependency(settings.AUTH_USER_MODEL),",
        "        ('appointments', '0004_appointment_booked_by'),",
        "        ('communication', '0004_device_registrations'),",
        "        ('interoperability', '0001_initial'),",
        "        ('operations', '0002_care_pathways_workforce_quality'),",
        "        ('registry', '0005_organization_license_dates'),",
        "        ('workforce', '0002_granular_permissions'),",
        "    ]",
        "",
        "    operations = [",
    ]

    for model in models:
        choices = text_choices(model)
        transformer = MigrationTransformer(model.name, model_names, choices)
        fields: list[tuple[str, str]] = []
        has_primary_key = False
        for child in model.body:
            if not isinstance(child, ast.Assign) or len(child.targets) != 1 or not isinstance(child.targets[0], ast.Name):
                continue
            if not isinstance(child.value, ast.Call):
                continue
            function_name = ast.unparse(child.value.func)
            if not function_name.startswith("models.") or not (
                function_name.endswith("Field") or function_name in {"models.ForeignKey", "models.OneToOneField", "models.ManyToManyField"}
            ):
                continue
            field_node = transformer.visit(ast.fix_missing_locations(child.value))
            ast.fix_missing_locations(field_node)
            if any(keyword.arg == "primary_key" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in field_node.keywords):
                has_primary_key = True
            fields.append((child.targets[0].id, ast.unparse(field_node)))
        if not has_primary_key:
            fields.insert(0, ("id", "models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')"))

        options: dict[str, str] = {}
        meta = next((child for child in model.body if isinstance(child, ast.ClassDef) and child.name == "Meta"), None)
        if meta:
            for key in ("ordering", "constraints", "indexes"):
                value = assignment_value(meta, key)
                if value is not None:
                    transformed = transformer.visit(ast.fix_missing_locations(value))
                    ast.fix_missing_locations(transformed)
                    options[key] = ast.unparse(transformed)

        lines.append("        migrations.CreateModel(")
        lines.append(f"            name='{model.name}',")
        lines.append("            fields=[")
        for field_name, field_expression in fields:
            lines.append(f"                ('{field_name}', {field_expression}),")
        lines.append("            ],")
        if options:
            lines.append("            options={")
            for key, expression in options.items():
                lines.append(f"                '{key}': {expression},")
            lines.append("            },")
        lines.append("        ),")
    lines.extend(["    ]", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when the committed migration differs from the models")
    args = parser.parse_args()
    output = migration_source()
    ast.parse(output)
    relative = TARGET.relative_to(ROOT)
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != output:
            raise SystemExit(f"{relative} is stale; run scripts/generate-enterprise-migration.py")
        print(f"Enterprise migration sync: {output.count('migrations.CreateModel(')} models passed")
        return
    TARGET.write_text(output, encoding="utf-8")
    print(f"Generated {relative} ({output.count('migrations.CreateModel(')} models)")


if __name__ == "__main__":
    main()
