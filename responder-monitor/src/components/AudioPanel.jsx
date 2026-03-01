import { useMonitor } from '../context/MonitorContext.jsx'

export default function AudioPanel() {
  const { stateConfig, liveAudioLevel } = useMonitor()

  if (!stateConfig) return null

  const {
    audioStatus, audioStatusColor, audioFillCls,
    cues, caption,
  } = stateConfig

  const displayLevel = Math.round(liveAudioLevel)

  return (
    <div className="panel" role="region" aria-label="Audio monitoring">
      <div className="panel-hd">
        <h2 className="panel-title">Audio</h2>
        <span className="panel-badge" style={{ color: audioStatusColor }}>
          {audioStatus}
        </span>
      </div>

      <div className="audio-body">
        {/* Level meter */}
        <div className="meter-row">
          <span className="meter-lbl" aria-hidden="true">Level</span>
          <div
            className="meter-track"
            role="meter"
            aria-label="Audio input level"
            aria-valuenow={displayLevel}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={`meter-fill ${audioFillCls}`}
              style={{ width: `${displayLevel}%` }}
            />
          </div>
          <span className="meter-val">{displayLevel || '—'}</span>
        </div>

        {/* Top cues */}
        <div className="cue-list" aria-label="Detected audio events" role="list">
          {cues.map((c, i) => (
            <div key={i} className="cue-row" role="listitem">
              <span className="cue-name">{c.name}</span>
              <div className="cue-bar" aria-hidden="true">
                <div
                  className={`cue-fill ${c.cls}`}
                  style={{ width: `${parseFloat(c.score) * 100 || 0}%` }}
                />
              </div>
              <span className="cue-score">{c.score}</span>
            </div>
          ))}
        </div>

        {/* Speech caption */}
        <div
          className="caption-box"
          role="log"
          aria-live="polite"
          aria-label="Transcribed speech"
        >
          <span className="fresh">{caption}</span>
        </div>
      </div>
    </div>
  )
}
