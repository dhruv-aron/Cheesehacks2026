import ThreatPanel    from './ThreatPanel.jsx'
import AudioPanel     from './AudioPanel.jsx'
import EventFeedPanel from './EventFeedPanel.jsx'

export default function Sidebar() {
  return (
    <aside className="sidebar" role="complementary" aria-label="Monitoring panels">
      <ThreatPanel />
      <AudioPanel />
      <EventFeedPanel />
    </aside>
  )
}
