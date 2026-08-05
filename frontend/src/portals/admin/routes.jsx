import { deepNav, deepRoutes } from '../deep/routes'
import Overview from './Overview'
import Users from './Users'
import AdminUserProfile from './AdminUserProfile'
import Appointments from './Appointments'
import Finance from './Finance'
import Reviews from './Reviews'
import Audit from './Audit'
import Compliance from './Compliance'
import Registry from './Registry'
import Operations from './Operations'
import NotificationConsole from '../operations/NotificationConsole'
import Subscriptions from '../operations/Subscriptions'
import SupportCentre from '../operations/SupportCentre'
import FinanceControls from '../operations/FinanceControls'
import EnterpriseAnalytics from '../operations/EnterpriseAnalytics'
import QualityCompliance from '../operations/QualityCompliance'
import EmergencyBoard from '../operations/EmergencyBoard'
import TheatreCases from '../operations/TheatreCases'
import AdminWorkflowWorkspace from './AdminWorkflowWorkspace'
import EnterpriseTools from './EnterpriseTools'
import IdentityCommandCentre from './IdentityCommandCentre'
import PrivilegedAccessCentre from './PrivilegedAccessCentre'
import ReleaseAcceptanceCentre from './ReleaseAcceptanceCentre'
import ResourceConsole from '../enterprise/ResourceConsole'
import { RESOURCE_FIELDS } from '../enterprise/roleCatalog'

const adminResourceModules = {
  cms: { label: 'Content & Experience CMS', icon: 'file', group: 'Platform services', description: 'Version banners, promotions, FAQs, legal pages, communication templates and service categories.', resourceName: 'content', fields: RESOURCE_FIELDS.content },
  integrations: { label: 'Integration Endpoints', icon: 'globe', group: 'Technology operations', description: 'Configure webhook, Kafka, RabbitMQ, FHIR, SFTP and warehouse destinations.', resourceName: 'integration-endpoints', fields: RESOURCE_FIELDS['integration-endpoints'] },
  schemas: { label: 'Event Schema Registry', icon: 'code', group: 'Technology operations', description: 'Govern versioned event contracts and compatibility.', resourceName: 'event-schemas', fields: RESOURCE_FIELDS['event-schemas'] },
  security: { label: 'Security & Resilience Operations', icon: 'shield', group: 'Trust & governance', description: 'Track scanning, backup, restore, penetration testing, DPIA and clinical safety evidence.', resourceName: 'security-operations', fields: RESOURCE_FIELDS['security-operations'] },
  verification: { label: 'AI Verification Review', icon: 'verified', group: 'Trust & governance', description: 'Review OCR fields, document quality, regulator responses, mismatch and fraud signals.', resourceName: 'verification-automation', fields: RESOURCE_FIELDS['verification-automation'] },
  mpi: { label: 'Master Patient Index', icon: 'users', group: 'Records administration', description: 'Manage canonical patient identities and normalized identifiers.', resourceName: 'patient-index', fields: RESOURCE_FIELDS['patient-index'] },
  providers: { label: 'Notification Provider Routing', icon: 'bell', group: 'Platform services', description: 'Prioritize email, SMS, WhatsApp, push and voice providers with health checks and failover.', resourceName: 'notification-providers', fields: RESOURCE_FIELDS['notification-providers'] },
  features: { label: 'Feature Configuration', icon: 'settings', group: 'Platform services', description: 'Control platform, organization, role and country feature settings.', resourceName: 'feature-config', fields: RESOURCE_FIELDS['feature-config'] },
}

const adminNav = [
  { to: '/admin/release-acceptance', label: 'Release Acceptance', icon: 'verified', group: 'Trust & governance', description: 'Formal workflow, privacy, safety, security and recovery sign-off', roles: ['admin', 'platform_super_admin', 'operations_admin', 'compliance_admin', 'clinical_safety_admin'] },
  { to: '/admin/privileged-access', label: 'Controlled Clinical Access', icon: 'shield', group: 'Trust & governance', description: 'Patient-specific, MFA-backed, time-limited administrator elevation', roles: ['admin', 'platform_super_admin', 'compliance_admin', 'clinical_safety_admin', 'operations_admin'] },
  { to: '/admin/identity-command', label: 'Identity Command Centre', icon: 'users', group: 'Identity & access', description: 'Global search, sessions, MFA, account state and scoped role contexts', roles: ['admin', 'platform_super_admin'] },
  { to: '/admin/enterprise-workflows', label: 'Enterprise Workflows', icon: 'activity', group: 'Care operations', description: 'All structured clinical and operational workflows' },
  { to: '/admin/enterprise-tools', label: 'Clinical & Data Tools', icon: 'settings', group: 'Platform services', description: 'Medication safety, MPI and FHIR tools' },
  { to: '/admin/cms', label: 'Content CMS', icon: 'file', group: 'Platform services', description: 'Banners, promotions, legal pages and templates' },
  { to: '/admin/integrations', label: 'Integration Platform', icon: 'globe', group: 'Platform services', description: 'Endpoints, events, schemas and partner delivery' },
  { to: '/admin/security-operations', label: 'Security Operations', icon: 'shield', group: 'Trust & governance', description: 'Security, backup, recovery and safety evidence' },
  { to: '/admin/ai-verification', label: 'AI Verification', icon: 'verified', group: 'Trust & governance', description: 'Automated credential pre-screening and review' },
  { to: '/admin/master-patient-index', label: 'Master Patient Index', icon: 'users', group: 'Identity & access', description: 'Canonical identity and duplicate management' },
  { to: '/admin/provider-routing', label: 'Provider Routing', icon: 'bell', group: 'Platform services', description: 'Notification health, priority and failover' },
  { to: '/admin/feature-configuration', label: 'Feature Configuration', icon: 'settings', group: 'Platform services', description: 'Country, role, organization and platform controls' },
  { to: '/admin', label: 'Command Centre', icon: 'dashboard', end: true, group: 'Overview', description: 'Platform health and operational metrics' },
  { to: '/admin/users', label: 'Users & Roles', icon: 'users', group: 'Identity & access', description: 'Patients, providers, staff and permissions' },
  { to: '/admin/registry', label: 'Provider Registry', icon: 'doctor', group: 'Identity & access', description: 'Verification, credentials and facilities' },
  { to: '/admin/operations', label: 'Hospital Operations', icon: 'hospital', group: 'Care operations', description: 'Admissions, beds, imaging, stock and procurement' },
  { to: '/admin/analytics', label: 'Enterprise Analytics', icon: 'chart', group: 'Overview', description: 'Clinical, operational, workforce and finance indicators' },
  { to: '/admin/emergency', label: 'Emergency Operations', icon: 'activity', group: 'Care operations', description: 'Emergency cases and ambulance dispatch' },
  { to: '/admin/theatre', label: 'Theatre Operations', icon: 'hospital', group: 'Care operations', description: 'Surgical cases and safety checks' },
  { to: '/admin/quality-incidents', label: 'Quality Incidents', icon: 'alert', group: 'Trust & governance', description: 'Safety, corrective actions and privacy requests' },
  { to: '/admin/appointments', label: 'Appointment Operations', icon: 'calendar', group: 'Care operations', description: 'Monitor appointments, no-shows and exceptions' },
  { to: '/admin/reviews', label: 'Quality & Reviews', icon: 'star', group: 'Care operations', description: 'Reviews, complaints and service quality' },
  { to: '/admin/finance-controls', label: 'Refunds & Adjustments', icon: 'audit', group: 'Finance', description: 'Approve and process financial exceptions' },
  { to: '/admin/subscriptions', label: 'Plans & Subscriptions', icon: 'wallet', group: 'Finance', description: 'Plans, limits, renewals and account status' },
  { to: '/admin/finance', label: 'Financial Management', icon: 'money', group: 'Finance', description: 'Transactions, commissions and payouts' },
  { to: '/admin/notifications', label: 'Notifications & Content', icon: 'bell', group: 'Platform services', description: 'Templates, broadcasts and announcements' },
  { to: '/admin/support', label: 'Support Operations', icon: 'help', group: 'Platform services', description: 'Support ticket triage and resolution' },
  { to: '/admin/compliance', label: 'Compliance & Privacy', icon: 'shield', group: 'Trust & governance', description: 'Consent, emergency access and policy controls' },
  { to: '/admin/audit', label: 'Audit Trail', icon: 'audit', group: 'Trust & governance', description: 'Security and clinical access history' },

  ...deepNav('admin', 'admin', { label: 'Complete page centre', group: 'Professional tools' }),

]

const SUPER_ADMIN_ROLES = ['admin', 'platform_super_admin']
const ADMIN_NAV_ACCESS = {
  '/admin/release-acceptance': ['admin', 'platform_super_admin', 'operations_admin', 'compliance_admin', 'clinical_safety_admin'],
  '/admin/privileged-access': ['admin', 'platform_super_admin', 'compliance_admin', 'clinical_safety_admin', 'operations_admin'],
  '/admin': ['admin', 'platform_super_admin', 'operations_admin', 'compliance_admin', 'clinical_safety_admin'],
  '/admin/operations': ['admin', 'platform_super_admin', 'operations_admin'],
  '/admin/analytics': ['admin', 'platform_super_admin', 'operations_admin', 'clinical_safety_admin'],
  '/admin/emergency': ['admin', 'platform_super_admin', 'operations_admin', 'clinical_safety_admin'],
  '/admin/theatre': ['admin', 'platform_super_admin', 'operations_admin', 'clinical_safety_admin'],
  '/admin/appointments': ['admin', 'platform_super_admin', 'operations_admin'],
  '/admin/subscriptions': ['admin', 'platform_super_admin', 'operations_admin'],
  '/admin/support': ['admin', 'platform_super_admin', 'operations_admin'],
  '/admin/quality-incidents': ['admin', 'platform_super_admin', 'clinical_safety_admin', 'compliance_admin'],
  '/admin/compliance': ['admin', 'platform_super_admin', 'compliance_admin'],
  '/admin/audit': ['admin', 'platform_super_admin', 'compliance_admin'],
  '/admin/security-operations': ['admin', 'platform_super_admin', 'compliance_admin'],
  '/admin/registry': ['admin', 'platform_super_admin', 'clinical_safety_admin'],
  '/admin/ai-verification': ['admin', 'platform_super_admin', 'clinical_safety_admin'],
  '/admin/enterprise-workflows': ['admin', 'platform_super_admin', 'operations_admin', 'clinical_safety_admin'],
  '/admin/finance': ['admin', 'platform_super_admin', 'operations_admin'],
  '/admin/finance-controls': ['admin', 'platform_super_admin', 'operations_admin'],
}
export const nav = adminNav.map((item) => ({ ...item, roles: item.roles || ADMIN_NAV_ACCESS[item.to] || SUPER_ADMIN_ROLES }))

export const routes = [
  { path: 'release-acceptance', element: <ReleaseAcceptanceCentre /> },
  { path: 'privileged-access', element: <PrivilegedAccessCentre /> },
  { path: 'identity-command', element: <IdentityCommandCentre /> },
  { path: 'enterprise-workflows', element: <AdminWorkflowWorkspace /> },
  { path: 'enterprise-tools', element: <EnterpriseTools /> },
  { path: 'cms', element: <ResourceConsole module={adminResourceModules.cms} /> },
  { path: 'integrations', element: <ResourceConsole module={adminResourceModules.integrations} /> },
  { path: 'event-schemas', element: <ResourceConsole module={adminResourceModules.schemas} /> },
  { path: 'security-operations', element: <ResourceConsole module={adminResourceModules.security} /> },
  { path: 'ai-verification', element: <ResourceConsole module={adminResourceModules.verification} /> },
  { path: 'master-patient-index', element: <ResourceConsole module={adminResourceModules.mpi} /> },
  { path: 'provider-routing', element: <ResourceConsole module={adminResourceModules.providers} /> },
  { path: 'feature-configuration', element: <ResourceConsole module={adminResourceModules.features} /> },
  { index: true, element: <Overview /> },
  { path: 'users', element: <Users /> },
  { path: 'users/:id', element: <AdminUserProfile /> },
  { path: 'analytics', element: <EnterpriseAnalytics /> },
  { path: 'emergency', element: <EmergencyBoard /> },
  { path: 'theatre', element: <TheatreCases /> },
  { path: 'quality-incidents', element: <QualityCompliance /> },
  { path: 'appointments', element: <Appointments /> },
  { path: 'operations', element: <Operations /> },
  { path: 'notifications', element: <NotificationConsole /> },
  { path: 'subscriptions', element: <Subscriptions admin /> },
  { path: 'support', element: <SupportCentre /> },
  { path: 'finance-controls', element: <FinanceControls /> },
  { path: 'finance', element: <Finance /> },
  { path: 'reviews', element: <Reviews /> },
  { path: 'audit', element: <Audit /> },
  { path: 'registry', element: <Registry /> },
  { path: 'compliance', element: <Compliance /> },

  ...deepRoutes('admin', 'admin', { title: 'Platform administration page centre' }),
]
