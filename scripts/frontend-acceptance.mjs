import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('frontend/src')
const files = []
const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
  const full = path.join(dir, entry.name)
  if (entry.isDirectory()) walk(full)
  else if (/\.(jsx?|tsx?)$/.test(entry.name)) files.push(full)
})
walk(root)

const failures = []
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8')
  const relative = path.relative(process.cwd(), file)
  if (/onClick=\{\(\)=>\{\s*\}\}/.test(text)) failures.push(`${relative}: empty click handler`)
  if (/confidence[^\n]{0,50}92%/i.test(text)) failures.push(`${relative}: hard-coded 92% confidence`)
  if (/Connected[^\n]{0,80}Live data/.test(text) && !/readiness|online|WebSocket/i.test(text)) failures.push(`${relative}: static connection status`)
}
const workflow = fs.readFileSync(path.join(root, 'portals/journeys/WorkflowCasePanel.jsx'), 'utf8')
for (const token of ['journeyApi.createCase', 'journeyApi.act', 'journeyApi.addComment', 'offline draft']) {
  if (!workflow.toLowerCase().includes(token.toLowerCase())) failures.push(`WorkflowCasePanel missing ${token}`)
}
const admin = fs.readFileSync(path.join(root, 'portals/admin/PrivilegedAccessCentre.jsx'), 'utf8')
for (const token of ['privilegedAccessApi.request', 'privilegedAccessApi.decide', 'EntitySearchSelect']) {
  if (!admin.includes(token)) failures.push(`PrivilegedAccessCentre missing ${token}`)
}
const releaseAcceptance = fs.readFileSync(path.join(root, 'portals/admin/ReleaseAcceptanceCentre.jsx'), 'utf8')
for (const token of ['journeyApi.productionReadiness', 'journeyApi.createReleaseAcceptance', 'FormData']) {
  if (!releaseAcceptance.includes(token)) failures.push(`ReleaseAcceptanceCentre missing ${token}`)
}
if (failures.length) {
  console.error('Frontend acceptance audit failed:')
  failures.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}
console.log(`Frontend acceptance audit: ${files.length} source files passed`)
