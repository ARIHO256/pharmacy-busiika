import EnterpriseDashboard from './EnterpriseDashboard'
import RecordWorkspace from './RecordWorkspace'
import ResourceConsole from './ResourceConsole'
import { portalForRole } from './roleCatalog'
import { deepNav, deepRoutes } from '../deep/routes'
import { sharedCoreForRole } from './sharedCore'

export function makeEnterprisePortal(role) {
  const portal = portalForRole(role)
  if (!portal) return null
  const shared = sharedCoreForRole(role, portal.path)
  return {
    portal,
    nav: [
      { to: `/${portal.path}`, label: 'Overview', icon: 'dashboard', end: true, group: 'Workspace', description: portal.description },
      ...shared.nav,
      ...portal.modules.map((module) => ({ to: `/${portal.path}/${module.id}`, label: module.label, icon: module.icon, group: module.group, description: module.description })),
      ...deepNav(portal.path, role, { label: 'Complete page centre', group: 'Professional tools' }),
      { to: '/notification-settings', label: 'Notification preferences', icon: 'bell', group: 'Settings', description: 'Choose channels, quiet hours and communication preferences.' },
      { to: '/security', label: 'Security centre', icon: 'shield', group: 'Settings', description: 'Password, MFA, sessions and security history.' },
    ],
    routes: [
      { index: true, element: <EnterpriseDashboard portal={portal}/> },
      ...shared.routes,
      ...portal.modules.map((module) => ({ path: module.id, element: module.kind === 'records' ? <RecordWorkspace module={module}/> : <ResourceConsole module={module}/> })),
      ...deepRoutes(portal.path, role, { title: `${portal.title} page centre` }),
    ],
  }
}
