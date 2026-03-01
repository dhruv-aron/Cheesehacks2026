import { useState, useCallback } from 'react'
import { useMonitor } from '../context/MonitorContext.jsx'

export default function TopBar() {
  const {
    stateConfig, currentStateName, isMuted, escLocked,
    markSafe, openModal, toggleMute, recordClip,
  } = useMonitor()

  const [safeFeedback, setSafeFeedback] = useState(false)
  const [clipLoading,  setClipLoading]  = useState(false)

  const handleMarkSafe = useCallback(() => {
    markSafe()
    setSafeFeedback(true)
    setTimeout(() => setSafeFeedback(false), 3500)
  }, [markSafe])

  const handleClip = useCallback(() => {
    setClipLoading(true)
    recordClip()
    setTimeout(() => setClipLoading(false), 1400)
  }, [recordClip])

  const offline = stateConfig?.offline ?? false

  return (
    <header className="topbar" role="banner">
      {/* Left: Logo */}
      <div className="tb-left">
        <div className="logo-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M12 2 3 7v6c0 5.25 3.75 10.15 9 11.25C17.25 23.15 21 18.25 21 13V7z" />
          </svg>
        </div>
        <div className="logo-copy">
          <div className="logo-name">Responder Monitor</div>
          <div className="logo-env">Unit 12 · Field</div>
        </div>
      </div>

      {/* Center: Connection status */}
      <div className="tb-center" role="status" aria-label="Stream connection status">
        <div className="conn-pill">
          <div className={`conn-dot${offline ? ' off' : ''}`} aria-hidden="true" />
          <span className={`conn-live${offline ? ' off' : ''}`}>
            {offline ? 'RECONNECTING' : 'LIVE'}
          </span>
          <span className="conn-latency">{offline ? '· —' : '· 240ms'}</span>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="tb-right" role="toolbar" aria-label="Primary actions">
        <button
          className={`btn btn-safe${safeFeedback ? ' feedback' : ''}`}
          title="Mark the current scene as safe. Logs an operator note."
          onClick={handleMarkSafe}
        >
          <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span className="btn-txt">{safeFeedback ? 'Marked Safe' : 'Mark Safe'}</span>
        </button>

        <button
          className={`btn btn-escalate${stateConfig?.escPulse && !escLocked ? ' pulsing' : ''}${escLocked ? ' locked' : ''}`}
          title="Escalate incident — requires confirmation."
          onClick={openModal}
          disabled={escLocked}
        >
          <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span className="btn-txt">{escLocked ? 'Escalated' : 'Escalate'}</span>
        </button>

        <button
          className="btn btn-ghost"
          style={isMuted ? { color: 'var(--elevated)' } : {}}
          title={isMuted ? 'Unmute audio' : 'Mute audio output'}
          onClick={toggleMute}
        >
          {isMuted ? (
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <line x1="23" y1="9" x2="17" y2="15" />
              <line x1="17" y1="9" x2="23" y2="15" />
            </svg>
          ) : (
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
            </svg>
          )}
          <span className="btn-txt">{isMuted ? 'Unmute' : 'Mute'}</span>
        </button>

        <button
          className="btn btn-ghost"
          title="Save last 30 seconds as a clip. Does not interrupt stream."
          onClick={handleClip}
          disabled={clipLoading}
        >
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <rect x="2" y="7" width="20" height="15" rx="2" />
            <polyline points="17 2 12 7 7 2" />
          </svg>
          <span className="btn-txt">{clipLoading ? 'Saving…' : 'Record Clip'}</span>
        </button>

        <button
          className="btn btn-ghost"
          title="Configure alerts, audio thresholds, and display."
        >
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          <span className="btn-txt">Settings</span>
        </button>
      </div>
    </header>
  )
}
