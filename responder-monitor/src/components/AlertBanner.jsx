import { useMonitor } from '../context/MonitorContext.jsx'

const EMERGENCY_CALL_ALERT_MS = 30_000

export default function AlertBanner() {
  const { stateConfig, alertDismissed, dismissAlert, emergencyCallAt } = useMonitor()

  const showEmergencyCall = emergencyCallAt != null && (Date.now() - emergencyCallAt) < EMERGENCY_CALL_ALERT_MS
  const showHighThreat = stateConfig?.showBanner && !alertDismissed

  if (showEmergencyCall) return null

  if (!showHighThreat) return null

  return (
    <div className="alert-banner" role="alert" aria-live="assertive">
      <div className="alert-dot" aria-hidden="true" />
      <span>High threat detected — review and escalate if needed.</span>
      <button className="alert-dismiss" onClick={dismissAlert} aria-label="Dismiss alert">✕</button>
    </div>
  )
}
