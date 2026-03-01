import { useId } from 'react'
import { useMonitor } from '../context/MonitorContext.jsx'

/* ── Derive live threat level from numeric score ──────────────────────── */
function deriveLiveLevel(score) {
  if (score >= 80) return { level: 'High', levelCls: 'high', sub: 'Immediate review required' }
  if (score >= 60) return { level: 'Elevated', levelCls: 'elevated', sub: 'Monitoring closely' }
  if (score >= 30) return { level: 'Moderate', levelCls: 'elevated', sub: 'Attention advised' }
  return { level: 'Low', levelCls: 'low', sub: 'All clear' }
}

/* ── Sparkline ───────────────────────────────────────────────────────── */
function ThreatSparkline({ data, color }) {
  const uid = useId()
  const W = 200, H = 26

  if (!data || data.length < 2) return <div className="spark-wrap" />

  const pts = data.map((v, i) => {
    const x = ((i / (data.length - 1)) * W).toFixed(1)
    const y = (H - (Math.min(100, Math.max(0, v)) / 100) * H).toFixed(1)
    return `${x},${y}`
  }).join(' ')

  const areaPoints = `0,${H} ${pts} ${W},${H}`
  const gradId = `sg-${uid.replace(/:/g, '')}`

  return (
    <div className="spark-wrap" role="img" aria-label="Threat score trend — last 60 seconds">
      <svg viewBox="0 0 200 26" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polyline
          points={pts}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.85"
        />
        <polygon points={areaPoints} fill={`url(#${gradId})`} />
      </svg>
    </div>
  )
}

export default function ThreatPanel() {
  const { stateConfig, sparkData, whyOpen, toggleWhy, backendConnected, liveScore } = useMonitor()

  if (!stateConfig) return null

  // When live backend is connected, derive everything from the real score
  const displayScore = backendConnected ? Math.round(liveScore) : stateConfig.score
  const { level, levelCls, sub } = backendConnected
    ? deriveLiveLevel(displayScore)
    : { level: stateConfig.level, levelCls: stateConfig.levelCls, sub: stateConfig.sub }

  const sparkColor = stateConfig.sparkColor
  const chips = stateConfig.chips
  const whyText = stateConfig.whyText

  return (
    <div className="panel" role="region" aria-label="Threat level">
      <div className="panel-hd">
        <h2 className="panel-title">
          Threat Level
          {backendConnected && (
            <span style={{ fontSize: '0.65rem', fontWeight: 400, color: 'var(--live)', marginLeft: '0.5rem' }}>
              ● LIVE
            </span>
          )}
        </h2>
        <button
          className="panel-action"
          onClick={toggleWhy}
          aria-expanded={whyOpen}
          aria-controls="why-drawer"
        >
          {whyOpen ? 'Close' : 'Why this?'}
        </button>
      </div>

      <div className="threat-body">
        <div className="score-row">
          <div
            className={`t-score ${levelCls}`}
            aria-label={`Threat score ${displayScore} out of 100`}
          >
            {displayScore}
          </div>
          <div className="score-meta">
            <div className={`t-level ${levelCls}`}>{level}</div>
            <div className="t-sub">{sub}</div>
          </div>
        </div>

        <ThreatSparkline data={sparkData} color={sparkColor} />

        <div className="chips" aria-label="Active threat indicators" role="list">
          {chips.map((c, i) => (
            <span key={i} className={`chip ${c.cls}`} role="listitem">
              {c.label}
              <span className="chip-score">{c.score}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Why this? drawer */}
      {whyOpen && (
        <div id="why-drawer" className="why-drawer" role="region" aria-label="Threat explanation">
          {whyText?.map((item, i) => (
            <p key={i}>
              <strong>{item.title}</strong> — {item.body}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

