import { useMonitor } from '../context/MonitorContext.jsx'

const BACKEND_URL = 'http://localhost:8000'

/* ── Player audio meter bars ─────────────────────────────────────────── */
function PlayerMeter({ level, visible }) {
  const N = 12
  return (
    <div
      className="p-meter"
      role="meter"
      aria-label="Audio level"
      aria-valuenow={Math.round(level)}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.2s' }}
    >
      {Array.from({ length: N }, (_, i) => {
        const threshold = (i / N) * 100
        const active = level > threshold
        const h = 5 + (i / N) * 14
        const col = threshold > 88
          ? 'var(--high)'
          : threshold > 68
            ? 'var(--elevated)'
            : 'var(--live)'
        return (
          <div
            key={i}
            className="p-meter-bar"
            style={{
              height: `${h}px`,
              background: active ? col : 'rgba(255,255,255,0.08)',
              opacity: active ? 1 : 0.5,
            }}
          />
        )
      })}
    </div>
  )
}

export default function VideoCard() {
  const {
    stateConfig, timestamp, liveAudioLevel,
    playerToggles, togglePlayer,
    backendConnected,
  } = useMonitor()

  const offline = stateConfig?.offline ?? false
  const { cc, bb, meter } = playerToggles

  return (
    <div className="video-card" role="region" aria-label="Camera feed">

      {/* Camera feed — live MJPEG or demo SVG */}
      <div className="cam-feed">
        {backendConnected ? (
          /* Live annotated MJPEG stream from backend */
          <img
            src={`${BACKEND_URL}/stream`}
            alt="Live annotated camera feed"
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
              display: 'block',
              borderRadius: '4px',
            }}
          />
        ) : (
          /* Demo mode: stylized silhouette placeholder */
          <>
            <div className="cam-grid" aria-hidden="true" />
            <svg
              className="cam-silhouettes"
              viewBox="0 0 800 450"
              preserveAspectRatio="xMidYMid meet"
              aria-hidden="true"
            >
              <g transform="translate(240,100)" fill="rgba(200,210,230,0.9)">
                <ellipse cx="0" cy="0" rx="14" ry="18" />
                <rect x="-18" y="20" width="36" height="70" rx="8" />
                <rect x="-26" y="26" width="14" height="48" rx="7" />
                <rect x="12" y="26" width="14" height="48" rx="7" />
                <rect x="-12" y="90" width="11" height="42" rx="5" />
                <rect x="1" y="90" width="11" height="42" rx="5" />
              </g>
              <g transform="translate(390,95)" fill="rgba(180,190,215,0.85)">
                <ellipse cx="0" cy="0" rx="13" ry="17" />
                <rect x="-16" y="19" width="32" height="65" rx="7" />
                <rect x="-23" y="24" width="13" height="44" rx="6" />
                <rect x="10" y="24" width="13" height="44" rx="6" />
                <rect x="-11" y="84" width="10" height="40" rx="5" />
                <rect x="1" y="84" width="10" height="40" rx="5" />
              </g>
              <g transform="translate(530,108)" fill="rgba(160,170,200,0.75)">
                <ellipse cx="0" cy="0" rx="12" ry="16" />
                <rect x="-15" y="18" width="30" height="60" rx="7" />
                <rect x="-21" y="22" width="12" height="40" rx="6" />
                <rect x="9" y="22" width="12" height="40" rx="6" />
                <rect x="-10" y="78" width="9" height="36" rx="5" />
                <rect x="1" y="78" width="9" height="36" rx="5" />
              </g>
            </svg>
            <div className="cam-vignette" aria-hidden="true" />
          </>
        )}
      </div>

      {/* Bounding boxes — only shown in demo mode; live frames have boxes baked in */}
      {!backendConnected && (
        <div
          className="bbox-layer"
          aria-hidden="true"
          style={{ opacity: bb ? 1 : 0 }}
        >
          <div className="bbox" style={{ left: '26%', top: '19%', width: '10%', height: '44%' }}>
            <div className="bbox-tag">Person · 0.94</div>
          </div>
          <div className="bbox" style={{ left: '44%', top: '18%', width: '9%', height: '40%' }}>
            <div className="bbox-tag">Person · 0.89</div>
          </div>
          <div className="bbox" style={{ left: '61%', top: '21%', width: '9%', height: '36%' }}>
            <div className="bbox-tag">Person · 0.77</div>
          </div>
        </div>
      )}

      {/* Top overlay: live badge + timestamp */}
      <div className="vid-top">
        <span
          className={`live-badge${offline ? ' offline' : ''}`}
          aria-label={offline ? 'Offline' : backendConnected ? 'Live stream connected' : 'Live stream'}
        >
          {offline ? 'OFFLINE' : backendConnected ? '● LIVE' : 'LIVE'}
        </span>
        <time className="vid-ts" aria-live="off">{timestamp}</time>
      </div>

      {/* PiP map */}
      <div
        className="pip-map"
        role="img"
        aria-label="Location: Main Corridor, Building C"
        title="Map location — Main Corridor · Bldg C"
      >
        <div className="pip-map-bg" />
        <div className="pip-ring" aria-hidden="true" />
        <div className="pip-dot" aria-hidden="true" />
        <div className="pip-label">Main Corridor · Bldg C</div>
      </div>

      {/* Player controls bar */}
      <div className="vid-controls" role="toolbar" aria-label="Player controls">
        <button
          className={`ptoggle${cc ? ' on' : ''}`}
          onClick={() => togglePlayer('cc')}
          aria-pressed={cc}
          title="Toggle speech captions"
        >
          <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <rect x="2" y="6" width="20" height="12" rx="2" />
            <path d="M7 12h4M15 12h2M7 15h2M13 15h4" />
          </svg>
          CC
        </button>

        {/* Boxes toggle only visible in demo mode */}
        {!backendConnected && (
          <button
            className={`ptoggle${bb ? ' on' : ''}`}
            onClick={() => togglePlayer('bb')}
            aria-pressed={bb}
            title="Toggle person detection overlay"
          >
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
            Boxes
          </button>
        )}

        <button
          className={`ptoggle${meter ? ' on' : ''}`}
          onClick={() => togglePlayer('meter')}
          aria-pressed={meter}
          title="Toggle audio level indicator"
        >
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          Meter
        </button>

        <PlayerMeter level={liveAudioLevel} visible={meter} />
      </div>

      {/* Offline overlay */}
      {offline && (
        <div className="offline-ov" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <div className="off-label">Reconnecting…</div>
          <div className="off-sub">Attempting to restore stream feed</div>
        </div>
      )}
    </div>
  )
}
