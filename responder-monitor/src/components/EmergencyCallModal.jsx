import { useEffect } from 'react'
import { useMonitor } from '../context/MonitorContext.jsx'

const EMERGENCY_CALL_ALERT_MS = 30_000

export default function EmergencyCallModal() {
  const { emergencyCallAt, dismissEmergencyCall } = useMonitor()

  const isActive = emergencyCallAt != null && (Date.now() - emergencyCallAt) < EMERGENCY_CALL_ALERT_MS

  useEffect(() => {
    if (!isActive) return
    const handler = (e) => { if (e.key === 'Escape') dismissEmergencyCall() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isActive, dismissEmergencyCall])

  if (!isActive) return null

  return (
    <div
      className="modal-bg modal-bg--emergency"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="emergency-call-title"
      onClick={e => { if (e.target === e.currentTarget) dismissEmergencyCall() }}
    >
      <div className="modal modal--emergency-call">
        <div className="modal-hd">
          <div className="modal-hd-icon modal-hd-icon--emergency" aria-hidden="true">
            <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
            </svg>
          </div>
          <div>
            <div className="modal-title" id="emergency-call-title">Emergency call to dispatch</div>
            <div className="modal-sub">Backup has been notified. A phone call is in progress with the threat overview.</div>
          </div>
        </div>
        <div className="modal-body">
          <p className="emergency-call-message">
            The automated system has placed an emergency call with the situation details. Officers have been notified.
          </p>
        </div>
        <div className="modal-ft">
          <button
            type="button"
            className="btn btn-esc-confirm"
            onClick={dismissEmergencyCall}
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
