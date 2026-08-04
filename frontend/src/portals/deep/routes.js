import React from 'react'
import DeepPageDirectory from './DeepPageDirectory'
import DeepWorkspacePage from './DeepWorkspacePage'
import { pagesForRole } from './pageCatalog'

export function deepNav(basePath, role, options = {}) {
  const pages = pagesForRole(role)
  if (!pages.length) return []
  const featured = pages.slice(0, options.featured || 4)
  return [
    { to: `/${basePath}/workspaces`, label: options.label || 'All role pages', icon: 'dashboard', group: options.group || 'Professional tools', description: 'Complete page directory for this role.' },
    ...featured.map((page) => ({ to: `/${basePath}/workspace/${page.slug}`, label: page.label, icon: page.icon, group: options.group || 'Professional tools', description: page.description })),
  ]
}

export function deepRoutes(basePath, role, options = {}) {
  const pages = pagesForRole(role)
  if (!pages.length) return []
  return [
    { path: 'workspaces', element: React.createElement(DeepPageDirectory, { pages, basePath, title: options.title || 'Professional page centre' }) },
    ...pages.map((page) => ({ path: `workspace/${page.slug}`, element: React.createElement(DeepWorkspacePage, { page, basePath }) })),
  ]
}
