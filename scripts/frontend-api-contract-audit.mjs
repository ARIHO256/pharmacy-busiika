import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('frontend/src')
const endpointFile = path.join(root, 'api/endpoints.js')
const endpointText = fs.readFileSync(endpointFile, 'utf8')
const failures = []

function objectBlock(name) {
  const marker = `export const ${name} = {`
  const start = endpointText.indexOf(marker)
  if (start < 0) return ''
  let depth = 0
  let quote = null
  let escaped = false
  const braceStart = endpointText.indexOf('{', start)
  for (let i = braceStart; i < endpointText.length; i += 1) {
    const ch = endpointText[i]
    if (quote) {
      if (escaped) escaped = false
      else if (ch === '\\') escaped = true
      else if (ch === quote) quote = null
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') { quote = ch; continue }
    if (ch === '{') depth += 1
    if (ch === '}') {
      depth -= 1
      if (depth === 0) return endpointText.slice(braceStart + 1, i)
    }
  }
  return ''
}

const apiNames = [...endpointText.matchAll(/export const\s+(\w+Api)\s*=\s*\{/g)].map((match) => match[1])
const methods = new Map()
for (const name of apiNames) {
  const block = objectBlock(name)
  methods.set(name, new Set([...block.matchAll(/^\s{2}(\w+)\s*:/gm)].map((match) => match[1])))
}

const files = []
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full)
    else if (/\.(js|jsx)$/.test(entry.name) && full !== endpointFile) files.push(full)
  }
}
walk(root)
let calls = 0
let explicitButtons = 0
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8')
  const relative = path.relative(process.cwd(), file)
  for (const match of text.matchAll(/\b(\w+Api)\.(\w+)\s*\(/g)) {
    calls += 1
    const [, api, method] = match
    if (!methods.has(api)) failures.push(`${relative}: unknown API object ${api}`)
    else if (!methods.get(api).has(method)) failures.push(`${relative}: ${api}.${method} is not declared in endpoints.js`)
  }
  for (const match of text.matchAll(/<(Button|button)\b([\s\S]*?)>/g)) {
    const [, tag, attrs] = match
    if (!/type\s*=\s*["']button["']/.test(attrs)) continue
    explicitButtons += 1
    const interactive = /onClick\s*=/.test(attrs) || /form\s*=/.test(attrs) || /disabled\s*=/.test(attrs)
    if (!interactive) failures.push(`${relative}: <${tag} type="button"> has no click/form/disabled contract`)
  }
}
if (failures.length) {
  console.error('Frontend API/action contract audit failed:')
  failures.forEach((failure) => console.error(`- ${failure}`))
  process.exit(1)
}
console.log(`Frontend API/action contract: ${calls} API calls and ${explicitButtons} explicit action buttons passed`)
