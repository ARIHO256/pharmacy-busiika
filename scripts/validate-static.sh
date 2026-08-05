#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m compileall -q -x '(^|/)\.venv/' backend
python3 - <<'PY'
import ast
from pathlib import Path
files=[path for path in Path('backend').rglob('*.py') if '.venv' not in path.parts and '__pycache__' not in path.parts]
errors=[]
for path in files:
    try: ast.parse(path.read_text(encoding='utf-8'))
    except Exception as exc: errors.append(f'{path}: {exc}')
if errors: raise SystemExit('\n'.join(errors))
print(f'Backend syntax: {len(files)} Python files passed')
PY

python3 - <<'PY'
import ast
from pathlib import Path
apps={}
for path in Path('backend').glob('*/migrations/[0-9]*_*.py'):
    apps.setdefault(path.parts[1], set()).add(path.stem)
errors=[]; count=0
for path in Path('backend').glob('*/migrations/[0-9]*_*.py'):
    count += 1
    tree=ast.parse(path.read_text(encoding='utf-8')); dependencies=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'dependencies' for t in node.targets):
            try: dependencies=ast.literal_eval(node.value)
            except Exception: dependencies=[]
            break
    for dependency in dependencies:
        if not isinstance(dependency, (tuple, list)) or len(dependency) != 2: continue
        app, migration=dependency
        if app in apps and migration not in apps[app] and migration not in {'__first__', '__latest__'}:
            errors.append(f'{path}: missing local dependency {app}.{migration}')
if errors: raise SystemExit('\n'.join(errors))
print(f'Migration dependency graph: {count} local migrations passed')
PY

python3 - <<'PY'
import ast
from pathlib import Path
errors=[]; checked=0
for urls in Path('backend').glob('*/urls.py'):
    tree=ast.parse(urls.read_text(encoding='utf-8'))
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 1 or not node.module: continue
        target=urls.parent / f'{node.module}.py'
        if not target.exists(): continue
        target_tree=ast.parse(target.read_text(encoding='utf-8'))
        defined={child.name for child in target_tree.body if isinstance(child,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))}
        for child in target_tree.body:
            if isinstance(child, (ast.Assign, ast.AnnAssign)):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                defined.update(target.id for target in targets if isinstance(target, ast.Name))
        imported={alias.name for alias in node.names if alias.name != '*'}
        missing=sorted(imported-defined)
        if missing: errors.append(f'{urls}: {node.module} does not define {", ".join(missing)}')
        checked += len(imported)
if errors: raise SystemExit('\n'.join(errors))
print(f'Backend URL import wiring: {checked} view symbols passed')
PY

TS="${TYPESCRIPT_JS:-/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js}"
if [[ -f "$TS" ]]; then
  TYPESCRIPT_JS="$TS" node <<'NODE'
const fs=require('fs'),path=require('path'),ts=require(process.env.TYPESCRIPT_JS)
const files=[]
function walk(dir){for(const item of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,item.name);if(item.isDirectory())walk(p);else if(/\.(js|jsx)$/.test(item.name))files.push(p)}}
walk('frontend/src')
const errors=[]
for(const file of files){const source=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,file.endsWith('.jsx')?ts.ScriptKind.JSX:ts.ScriptKind.JS);for(const diagnostic of source.parseDiagnostics||[])errors.push(`${file}: ${ts.flattenDiagnosticMessageText(diagnostic.messageText,' ')}`)}
if(errors.length){console.error(errors.join('\n'));process.exit(1)}
console.log(`Frontend syntax: ${files.length} JavaScript/JSX files passed`)
NODE
else
  echo "TypeScript parser not found; run npm ci && npm run build for frontend validation."
fi


python3 scripts/generate-enterprise-migration.py --check
python3 scripts/audit-role-portals.py
node scripts/audit-deep-pages.mjs

python3 - <<'PY'
import re
from pathlib import Path
pattern=re.compile(r'''(?:from\s+|import\s*\()?["'](\.{1,2}/[^"']+)["']''')
errors=[]
for source in Path('frontend/src').rglob('*'):
    if source.suffix not in {'.js','.jsx'}: continue
    for relative in pattern.findall(source.read_text(encoding='utf-8')):
        target=source.parent/relative
        candidates=(target,target.with_suffix('.js'),target.with_suffix('.jsx'),target/'index.js',target/'index.jsx')
        if not any(path.exists() for path in candidates): errors.append(f'{source}: missing {relative}')
if errors: raise SystemExit('\n'.join(errors))
print('Frontend relative imports: passed')
PY

python3 - <<'PY'
import json
from pathlib import Path
json.loads(Path('frontend/package.json').read_text(encoding='utf-8'))
print('JSON manifests: passed')
PY

python3 - <<'PY'
from pathlib import Path
try:
    import yaml
except ImportError:
    print('PyYAML unavailable; Docker Compose YAML validation skipped')
else:
    yaml.safe_load(Path('docker-compose.yml').read_text(encoding='utf-8'))
    yaml.safe_load(Path('deploy/prometheus.yml').read_text(encoding='utf-8'))
    print('Docker Compose and Prometheus YAML: passed')
PY

if grep -RIn --exclude-dir=.venv --exclude-dir=__pycache__ --exclude='*.pyc' 'NotImplementedError' backend frontend/src >/tmp/healthpilot-notimplemented.txt; then
  cat /tmp/healthpilot-notimplemented.txt
  echo 'NotImplementedError markers are not permitted in the release tree.' >&2
  exit 1
fi

for file in .env.compose .env.production.example backend/.env.example frontend/.env.example frontend/package.json frontend/package-lock.json backend/requirements.txt docs/IMPLEMENTATION_STATUS_21_SECTIONS.md docs/RUNTIME_ACCEPTANCE_CHECKLIST.md; do test -s "$file"; done
while IFS= read -r script; do bash -n "$script"; done < <(find . -path './backend/.venv' -prune -o -type f -name '*.sh' -print)
python3 scripts/workflow-completion-audit.py
python3 scripts/authorization-audit.py
node scripts/frontend-acceptance.mjs
node scripts/frontend-api-contract-audit.mjs

echo "Static validation completed successfully."
