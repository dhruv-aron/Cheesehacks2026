import { useMonitor } from '../context/MonitorContext.jsx'
import VideoCard from './VideoCard.jsx'

export default function PlayerColumn() {
  const { stateConfig, sceneAgeSec } = useMonitor()

  const ageLabel = sceneAgeSec < 60
    ? `${sceneAgeSec}s ago`
    : `${Math.floor(sceneAgeSec / 60)}m ago`

  return (
    <section className="player-col" aria-label="Live video">
      <VideoCard />

      <div
        className="scene-strip"
        role="status"
        aria-live="polite"
        aria-label="Scene summary"
      >
        <svg
          fill="none" stroke="currentColor" strokeWidth="2"
          viewBox="0 0 24 24" aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>

        <p
          className="scene-txt"
          dangerouslySetInnerHTML={{ __html: stateConfig?.sceneHtml ?? '' }}
        />

        <span className="scene-age">{ageLabel}</span>
      </div>
    </section>
  )
}
