import { useState } from 'react'
import HealthIcon from '../icons/HealthIcon'

export default function SupportWidget() {
  const [open, setOpen] = useState(false)

  return (
    <div className="support-widget">
      {open && (
        <section className="support-panel" aria-label="Help and support">
          <div className="support-panel-head">
            <div>
              <small>HEALTHPILOT SUPPORT</small>
              <strong>How can we help?</strong>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close support"><HealthIcon name="close" size={18}/></button>
          </div>
          <div className="support-emergency">
            <HealthIcon name="alert" size={20}/>
            <p><strong>Medical emergency?</strong><span>Do not wait for chat support. Contact your local emergency service or go to the nearest emergency facility.</span></p>
          </div>
          <a href="mailto:support@healthpilot.health" className="support-option">
            <span><HealthIcon name="message" size={19}/></span>
            <div><strong>Contact support</strong><small>Account, booking and payment assistance</small></div>
            <HealthIcon name="chevron" size={16}/>
          </a>
          <a href="/" className="support-option">
            <span><HealthIcon name="file" size={19}/></span>
            <div><strong>Help centre</strong><small>Guides for patients and providers</small></div>
            <HealthIcon name="chevron" size={16}/>
          </a>
          <div className="support-status"><i/> Systems operational</div>
        </section>
      )}
      <button type="button" className="support-trigger" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <HealthIcon name={open ? 'close' : 'help'} size={19}/>
        <span>{open ? 'Close' : 'Help & Support'}</span>
      </button>
    </div>
  )
}
