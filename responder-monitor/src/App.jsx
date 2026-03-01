import React, { useState, useEffect, useRef } from 'react';

const BACKEND_URL = 'http://localhost:8000';

export default function App() {
  const [score, setScore] = useState(0);
  const [events, setEvents] = useState([]);
  const seenEvents = useRef(new Set());

  // Polling score
  useEffect(() => {
    const fetchScore = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/score`);
        if (res.ok) {
          const data = await res.json();
          setScore(data.score ?? 0);
        }
      } catch (err) {
        console.error("Failed to fetch score:", err);
      }
    };

    fetchScore();
    const interval = setInterval(fetchScore, 1000);
    return () => clearInterval(interval);
  }, []);

  // Polling events
  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/events`);
        if (res.ok) {
          const data = await res.json();
          if (data.events && Array.isArray(data.events)) {
            const newEvents = [];
            data.events.forEach(ev => {
              const key = `${ev.type}-${ev.timestamp}`;
              if (!seenEvents.current.has(key)) {
                seenEvents.current.add(key);
                newEvents.push(ev);
              }
            });
            if (newEvents.length > 0) {
              setEvents(prev => [...newEvents, ...prev].slice(0, 50)); // Keep latest 50
            }
          }
        }
      } catch (err) {
        console.error("Failed to fetch events:", err);
      }
    };

    fetchEvents();
    const interval = setInterval(fetchEvents, 2000);
    return () => clearInterval(interval);
  }, []);

  // Determine styling based on score
  let statusClass = 'low';
  let statusText = 'SAFE';
  if (score >= 70) {
    statusClass = 'high';
    statusText = 'DANGER';
  } else if (score >= 30) {
    statusClass = 'medium';
    statusText = 'ELEVATED';
  }

  return (
    <div className="dashboard-container">
      <div className={`video-section danger-${statusClass}`}>
        <img
          src={`http://localhost:8000/stream`}
          alt="Live Camera Feed"
          className="video-stream"
          onError={(e) => {
            // Fallback black frame if stream is down
            e.target.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100%25' height='100%25' fill='black'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%23333' font-family='sans-serif' font-size='5'%3EStream Offline%3C/text%3E%3C/svg%3E";
          }}
        />
        <div className="video-overlay">
          <div className="live-badge">
            <div className="live-dot"></div>
            LIVE FEED
          </div>
        </div>
      </div>

      <div className="sidebar-section">
        <div className="glass-panel score-panel">
          <div className={`score-glow ${statusClass}`}></div>
          <div className="score-label">Aggregate Risk Score</div>
          <div className={`score-value ${statusClass}`}>{Math.round(score)}</div>
          <div className={`score-status ${statusClass}`}>{statusText}</div>
        </div>

        <div className="glass-panel events-panel">
          <div className="events-header">
            <span>Recent Events</span>
            <span className="events-count">{events.length}</span>
          </div>
          <div className="events-list">
            {events.length === 0 ? (
              <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '2rem' }}>
                Waiting for events...
              </div>
            ) : (
              events.map((ev, idx) => (
                <div key={`${ev.type}-${ev.timestamp}-${idx}`} className="event-card">
                  <div className="event-header">
                    <span className={`event-type ${ev.type}`}>{ev.type}</span>
                    <span className="event-time">{ev.formatted_time || new Date(ev.timestamp * 1000).toLocaleTimeString()}</span>
                  </div>
                  <div className="event-desc">{ev.message}</div>
                  {ev.score !== undefined && ev.score !== null && (
                    <div className="event-score">Confidence: {Math.round(ev.score)}%</div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
