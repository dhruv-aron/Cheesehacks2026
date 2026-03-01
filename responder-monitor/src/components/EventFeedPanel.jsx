import { useRef, useEffect, useCallback } from 'react'
import { useMonitor } from '../context/MonitorContext.jsx'

const FILTERS = ['all', 'audio', 'video', 'risk', 'system', 'user']

const ICONS = {
  audio: (
    <svg className="fi-icon audio" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  ),
  video: (
    <svg className="fi-icon video" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <polygon points="23 7 16 12 23 17 23 7" />
      <rect x="1" y="5" width="15" height="14" rx="2" />
    </svg>
  ),
  risk: (
    <svg className="fi-icon risk" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  system: (
    <svg className="fi-icon system" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  ),
  user: (
    <svg className="fi-icon user" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
}

function FeedItem({ event }) {
  const { id, time, type, label, text, score, variant } = event
  const labelCls = variant === 'escalated' ? 'fi-label-escalated' : 'fi-label'

  return (
    <div
      className="feed-item"
      title="Click to jump to this moment in buffer"
      role="article"
    >
      {ICONS[type] ?? ICONS.system}
      <div className="fi-body">
        <div className="fi-time">{time}</div>
        <div className="fi-text">
          <span className={labelCls}>{label}</span>
          {' '}{text}
          {score && <span className="fi-score"> ({score})</span>}
        </div>
      </div>
    </div>
  )
}

export default function EventFeedPanel() {
  const { events, filter, search, setFilter, setSearch } = useMonitor()
  const listRef = useRef(null)
  const prevCountRef = useRef(events.length)

  const filtered = events.filter(e => {
    const typeOk = filter === 'all' || e.type === filter
    const q = search.toLowerCase()
    const queryOk = !q || e.label.toLowerCase().includes(q) || e.text.toLowerCase().includes(q) || e.time.includes(q)
    return typeOk && queryOk
  })

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (!listRef.current) return
    if (events.length > prevCountRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
    prevCountRef.current = events.length
  }, [events.length])

  return (
    <div className="feed-panel" role="region" aria-label="Live event feed">
      <div className="panel-hd">
        <h2 className="panel-title">Live Feed</h2>
        <span className="panel-badge">{events.length} events</span>
      </div>

      <div className="feed-controls">
        <div className="feed-search" role="search">
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="search"
            placeholder="Search events…"
            aria-label="Filter event feed"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <div className="feed-tabs" role="tablist" aria-label="Filter by event type">
          {FILTERS.map(f => (
            <button
              key={f}
              className={`feed-tab${filter === f ? ' active' : ''}`}
              role="tab"
              aria-selected={filter === f}
              onClick={() => setFilter(f)}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div
        className="feed-list"
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-label="Event log"
      >
        {filtered.map(ev => (
          <FeedItem key={ev.id} event={ev} />
        ))}
      </div>
    </div>
  )
}
