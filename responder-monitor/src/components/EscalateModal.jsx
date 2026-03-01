import { useEffect } from 'react'
import { useMonitor } from '../context/MonitorContext.jsx'

const THUMBS = [
  { label: '−10s', bg: 'linear-gradient(135deg,#080a0e,#14161c)' },
  { label: '−7s',  bg: 'linear-gradient(135deg,#0b0d12,#181a22)' },
  { label: '−4s',  bg: 'linear-gradient(135deg,#090b10,#161820)' },
  { label: '−1s',  bg: 'linear-gradient(135deg,#0a0c12,#18191e)' },
]

export default function EscalateModal() {
  const {
    modalOpen, escLoading, stateConfig,
    closeModal, confirmEscalate,
  } = useMonitor()

  // Close on Escape key
  useEffect(() => {
    if (!modalOpen) return
    const handler = (e) => { if (e.key === 'Escape') closeModal() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [modalOpen, closeModal])

  if (!modalOpen) return null

  const { score, level, sub, chips } = stateConfig ?? {}
  const reasonsText = chips?.map(c => `${c.label} (${c.score})`).join(' · ') ?? ''

  return (
    <div
      className="modal-bg"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      onClick={e => { if (e.target === e.currentTarget) closeModal() }}
    >
      <div className="modal">
        {/* Header */}
        <div className="modal-hd">
          <div className="modal-hd-icon" aria-hidden="true">
            <svg width="16" height="16" fill="none" stroke="#ef4444" strokeWidth="2.5" viewBox="0 0 24 24">
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>
          <div>
            <div className="modal-title" id="modal-title">Escalate Incident</div>
            <div className="modal-sub">Review before escalating. This notifies dispatch immediately.</div>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Risk summary */}
          <div className="modal-score-row">
            <div className="modal-big-score">{score}</div>
            <div className="modal-score-info">
              <div className="modal-score-lbl">{level} — {sub}</div>
              <div className="modal-score-why">{reasonsText}</div>
            </div>
          </div>

          {/* Last 10s thumbnails */}
          <div>
            <div className="modal-thumb-lbl">LAST 10 SECONDS</div>
            <div className="modal-thumbs">
              {THUMBS.map(t => (
                <div key={t.label} className="m-thumb">
                  <div className="m-thumb-inner" style={{ background: t.bg }} />
                  <div className="m-thumb-ts">{t.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Warning */}
          <div className="modal-warn">
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <p className="modal-warn-txt">
              <strong>A false escalation is logged and reviewed.</strong>{' '}
              Only escalate if the threat is real and immediate.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-ft">
          <button className="btn btn-cancel" onClick={closeModal}>
            Cancel
          </button>
          <button
            className="btn btn-esc-confirm"
            onClick={confirmEscalate}
            disabled={escLoading}
          >
            <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" width="12" height="12">
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            </svg>
            {escLoading ? 'Escalating…' : 'Confirm Escalate'}
          </button>
        </div>
      </div>
    </div>
  )
}
