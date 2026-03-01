import { useMonitor } from '../context/MonitorContext.jsx'

export default function AlertBanner() {
  const { stateConfig, alertDismissed, dismissAlert } = useMonitor()

  if (!stateConfig?.showBanner || alertDismissed) return null

  return (
    <div className="alert-banner" role="alert" aria-live="assertive">
      <div className="alert-dot" aria-hidden="true" />
      <span>High threat detected — review and escalate if needed.</span>
      <button className="alert-dismiss" onClick={dismissAlert} aria-label="Dismiss alert">✕</button>
    </div>
  )
}
