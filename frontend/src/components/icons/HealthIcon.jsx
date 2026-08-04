import React from 'react'

const paths = {
  home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V21h13V10.5M9.5 21v-6h5v6"/></>,
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4.2-4.2"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></>,
  doctor: <><circle cx="12" cy="8" r="4"/><path d="M5 21v-2a7 7 0 0 1 14 0v2M9 3h6M12 3v2"/></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/></>,
  user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
  shield: <><path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>,
  video: <><rect x="3" y="6" width="13" height="12" rx="3"/><path d="m16 10 5-3v10l-5-3"/></>,
  message: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3 1.5-5A7 7 0 0 1 3 12V8a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M8 11h.01M12 11h.01M16 11h.01"/></>,
  prescription: <><path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h3"/><path d="m14 16 4 4m0-4-4 4"/></>,
  file: <><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></>,
  heart: <><path d="M20.8 4.7a5.5 5.5 0 0 0-7.8 0L12 5.8l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.4 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/><path d="M7 12h3l1.4-3 2.2 6 1.4-3h2"/></>,
  pill: <><path d="m10.5 4.5 9 9a4.2 4.2 0 0 1-6 6l-9-9a4.2 4.2 0 0 1 6-6Z"/><path d="m8 14 6-6"/></>,
  flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3"/><path d="M8 15h8"/></>,
  building: <><path d="M4 21V7l8-4 8 4v14M8 10h1M15 10h1M8 14h1M15 14h1M9 21v-4h6v4"/></>,
  bed: <><path d="M3 20v-8M21 20v-6a3 3 0 0 0-3-3H9v9M3 16h18M6 11V8h3a3 3 0 0 1 3 3"/></>,
  wallet: <><path d="M4 6h14a2 2 0 0 1 2 2v11H5a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3h12"/><path d="M15 11h7v5h-7a2.5 2.5 0 0 1 0-5Z"/></>,
  money: <><rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="12" cy="12" r="3"/><path d="M7 9H6v1M17 15h1v-1"/></>,
  invoice: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2Z"/><path d="M9 8h6M9 12h6M9 16h3"/></>,
  chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
  star: <><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.8 1.8 0 0 0 .4 2l.1.1-2.8 2.8-.1-.1a1.8 1.8 0 0 0-2-.4 1.8 1.8 0 0 0-1.1 1.6V21H10v-.1A1.8 1.8 0 0 0 9 19.4a1.8 1.8 0 0 0-2 .4l-.1.1-2.8-2.8.1-.1a1.8 1.8 0 0 0 .4-2A1.8 1.8 0 0 0 3 13.9H3V10h.1A1.8 1.8 0 0 0 4.6 9a1.8 1.8 0 0 0-.4-2l-.1-.1 2.8-2.8.1.1a1.8 1.8 0 0 0 2 .4A1.8 1.8 0 0 0 10.1 3V3H14v.1A1.8 1.8 0 0 0 15 4.6a1.8 1.8 0 0 0 2-.4l.1-.1 2.8 2.8-.1.1a1.8 1.8 0 0 0-.4 2 1.8 1.8 0 0 0 1.6 1.1h.1V14H21a1.8 1.8 0 0 0-1.6 1Z"/></>,
  audit: <><path d="M7 3h10v4H7zM5 5H4v16h16V5h-1"/><path d="M8 12h8M8 16h5"/></>,
  clipboard: <><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h3"/></>,
  box: <><path d="m4 7 8-4 8 4-8 4Z"/><path d="m4 7 8 4 8-4v10l-8 4-8-4Z"/><path d="M12 11v10"/></>,
  truck: <><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></>,
  hospital: <><path d="M4 21V5h16v16M9 3h6v5H9zM11 4v3M10 5h4M8 12h2M14 12h2M8 16h2M14 16h2M10 21v-3h4v3"/></>,
  insurance: <><path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z"/><path d="M12 8v8M8 12h8"/></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5"/></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
  close: <><path d="m6 6 12 12M18 6 6 18"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>,
  plus: <><path d="M12 5v14M5 12h14"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  more: <><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/></>,
  help: <><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.4 2.4 0 1 1 3.8 2c-1 .6-1.6 1.1-1.6 2.4M12 17h.01"/></>,
  globe: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></>,
  activity: <><path d="M3 12h4l2-6 4 12 2-6h6"/></>,
  alert: <><path d="M12 3 2.8 20h18.4Z"/><path d="M12 9v5M12 17h.01"/></>,
  filter: <><path d="M4 5h16M7 12h10M10 19h4"/></>,
  download: <><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></>,
  send: <><path d="m3 3 18 9-18 9 4-9Z"/><path d="M7 12h14"/></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 8a7 7 0 0 1 11.8-2L20 8M4 16l2.1 2a7 7 0 0 0 11.8-2"/></>,
}

export default function HealthIcon({ name = 'heart', size = 20, className = '', strokeWidth = 1.8 }) {
  if (typeof name === 'string' && /\p{Extended_Pictographic}/u.test(name)) {
    return <span className={className} style={{ fontSize: size, lineHeight: 1 }} aria-hidden="true">{name}</span>
  }
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.heart}
    </svg>
  )
}
