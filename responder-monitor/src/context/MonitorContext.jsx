import {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from 'react'
import { STATES, LIVE_EVENT_TEMPLATES } from '../data/states.js'
import { INITIAL_FEED_EVENTS, makeEvent } from '../data/feedEvents.js'

/* ── Helpers ─────────────────────────────────────────────────────────── */
function nowTs() {
  return new Date().toLocaleTimeString('en-US', { hour12: false })
}

function buildSparkData(base, length = 60) {
  const data = []
  for (let i = 0; i < length; i++) {
    const t = i / (length - 1)
    data.push(Math.max(0, Math.min(100, (base - 30) * t + Math.random() * 14 - 7 + 8)))
  }
  return data
}

/* ── Reducer ─────────────────────────────────────────────────────────── */
function reducer(state, action) {
  switch (action.type) {

    case 'SET_STATE': {
      const { name, sparkData } = action.payload
      const cfg = STATES[name]
      return {
        ...state,
        currentStateName: name,
        sparkData,
        liveAudioLevel: cfg.audioLevel,
        sceneAgeSec: 0,
        alertDismissed: false,
        whyOpen: false,
      }
    }

    case 'TICK_CLOCK':
      return { ...state, timestamp: action.payload, sceneAgeSec: state.sceneAgeSec + 1 }

    case 'LIVE_TICK': {
      const { newPoint, newAudioLevel } = action.payload
      const next = [...state.sparkData.slice(-59), newPoint]
      return { ...state, sparkData: next, liveAudioLevel: newAudioLevel }
    }

    case 'ADD_EVENT':
      return { ...state, events: [...state.events, action.payload] }

    case 'SET_FILTER':
      return { ...state, filter: action.payload }

    case 'SET_SEARCH':
      return { ...state, search: action.payload }

    case 'TOGGLE_WHY':
      return { ...state, whyOpen: !state.whyOpen }

    case 'TOGGLE_MUTE':
      return { ...state, isMuted: !state.isMuted }

    case 'TOGGLE_PLAYER': {
      const key = action.payload
      return { ...state, playerToggles: { ...state.playerToggles, [key]: !state.playerToggles[key] } }
    }

    case 'OPEN_MODAL':
      return { ...state, modalOpen: true }

    case 'CLOSE_MODAL':
      return { ...state, modalOpen: false, escLoading: false }

    case 'ESC_LOADING':
      return { ...state, escLoading: true }

    case 'ESC_CONFIRM': {
      const ev = makeEvent({
        type: 'risk',
        label: 'ESCALATED',
        text: `Dispatch notified. Score: ${action.payload.score}`,
        variant: 'escalated',
      })
      return {
        ...state,
        escLoading: false,
        escLocked: true,
        modalOpen: false,
        events: [...state.events, ev],
      }
    }

    case 'MARK_SAFE': {
      const ev = makeEvent({ type: 'user', label: 'Operator:', text: 'Scene marked safe' })
      return { ...state, alertDismissed: true, events: [...state.events, ev] }
    }

    case 'CLIP_DONE': {
      const ev = makeEvent({
        type: 'system',
        label: 'Clip saved',
        text: `Last 30s · clip_${action.payload.id}.mp4`,
      })
      return { ...state, events: [...state.events, ev] }
    }

    case 'DISMISS_ALERT':
      return { ...state, alertDismissed: true }

    default:
      return state
  }
}

/* ── Initial state ───────────────────────────────────────────────────── */
function buildInitialState() {
  const name = 'elevated'
  const cfg  = STATES[name]
  return {
    currentStateName: name,
    events: INITIAL_FEED_EVENTS,
    filter: 'all',
    search: '',
    isMuted: false,
    playerToggles: { cc: true, bb: true, meter: true },
    whyOpen: false,
    escLocked: false,
    escLoading: false,
    modalOpen: false,
    alertDismissed: false,
    sparkData: buildSparkData(cfg.sparkBase),
    liveAudioLevel: cfg.audioLevel,
    timestamp: nowTs(),
    sceneAgeSec: 0,
  }
}

/* ── Context ─────────────────────────────────────────────────────────── */
const MonitorContext = createContext(null)

export function useMonitor() {
  const ctx = useContext(MonitorContext)
  if (!ctx) throw new Error('useMonitor must be used inside MonitorProvider')
  return ctx
}

export function MonitorProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, undefined, buildInitialState)

  // Stable ref so effects can read currentStateName without re-subscribing
  const stateNameRef = useRef(state.currentStateName)
  stateNameRef.current = state.currentStateName

  /* Clock tick — every 1s */
  useEffect(() => {
    const id = setInterval(() => {
      dispatch({ type: 'TICK_CLOCK', payload: nowTs() })
    }, 1000)
    return () => clearInterval(id)
  }, [])

  /* Live event + sparkline tick — every 3.2s */
  useEffect(() => {
    const id = setInterval(() => {
      const name = stateNameRef.current
      if (name === 'reconnecting') return

      const cfg       = STATES[name]
      const templates = LIVE_EVENT_TEMPLATES[name] ?? []

      // Randomly add a feed event
      if (templates.length > 0 && Math.random() < 0.68) {
        const tpl = templates[Math.floor(Math.random() * templates.length)]
        const ev = makeEvent({
          type:  tpl.type,
          label: tpl.label,
          text:  tpl.makeText(cfg),
          score: tpl.score ? tpl.score() : null,
        })
        dispatch({ type: 'ADD_EVENT', payload: ev })
      }

      // Sparkline + audio level
      const newPoint      = Math.max(0, Math.min(100, cfg.sparkBase + (Math.random() * 14 - 7)))
      const variation     = (Math.random() - 0.45) * 18
      const newAudioLevel = Math.max(0, Math.min(100, cfg.audioLevel + (Math.random() * 16 - 8) + variation * 0.3))
      dispatch({ type: 'LIVE_TICK', payload: { newPoint, newAudioLevel } })
    }, 3200)
    return () => clearInterval(id)
  }, [])

  /* Reconnect system messages — every 5s while reconnecting */
  useEffect(() => {
    const id = setInterval(() => {
      if (stateNameRef.current !== 'reconnecting') return
      dispatch({
        type: 'ADD_EVENT',
        payload: makeEvent({ type: 'system', label: 'System:', text: 'Attempting reconnect…' }),
      })
    }, 5000)
    return () => clearInterval(id)
  }, [])

  /* ── Actions ──────────────────────────────────────────────────────── */
  const applyState = useCallback((name) => {
    const sparkData = buildSparkData(STATES[name].sparkBase)
    dispatch({ type: 'SET_STATE', payload: { name, sparkData } })

    if (name === 'reconnecting') {
      dispatch({
        type: 'ADD_EVENT',
        payload: makeEvent({ type: 'system', label: 'System:', text: 'Stream disconnected — attempting reconnect' }),
      })
    }
    if (name === 'high') {
      dispatch({
        type: 'ADD_EVENT',
        payload: makeEvent({ type: 'risk', label: 'Risk:', text: 'High (89) — physical altercation likely' }),
      })
    }
  }, [])

  const markSafe       = useCallback(() => dispatch({ type: 'MARK_SAFE' }), [])
  const openModal      = useCallback(() => dispatch({ type: 'OPEN_MODAL' }), [])
  const closeModal     = useCallback(() => dispatch({ type: 'CLOSE_MODAL' }), [])
  const toggleMute     = useCallback(() => dispatch({ type: 'TOGGLE_MUTE' }), [])
  const toggleWhy      = useCallback(() => dispatch({ type: 'TOGGLE_WHY' }), [])
  const dismissAlert   = useCallback(() => dispatch({ type: 'DISMISS_ALERT' }), [])
  const setFilter      = useCallback((f) => dispatch({ type: 'SET_FILTER', payload: f }), [])
  const setSearch      = useCallback((q) => dispatch({ type: 'SET_SEARCH', payload: q }), [])
  const togglePlayer   = useCallback((k) => dispatch({ type: 'TOGGLE_PLAYER', payload: k }), [])

  const confirmEscalate = useCallback(() => {
    dispatch({ type: 'ESC_LOADING' })
    setTimeout(() => {
      const score = STATES[stateNameRef.current]?.score ?? 62
      dispatch({ type: 'ESC_CONFIRM', payload: { score } })
    }, 1100)
  }, [])

  const recordClip = useCallback(() => {
    setTimeout(() => {
      const id = Date.now().toString(36).toUpperCase()
      dispatch({ type: 'CLIP_DONE', payload: { id } })
    }, 1400)
  }, [])

  const value = useMemo(() => ({
    ...state,
    stateConfig: STATES[state.currentStateName],
    // actions
    applyState,
    markSafe,
    openModal,
    closeModal,
    toggleMute,
    toggleWhy,
    dismissAlert,
    setFilter,
    setSearch,
    togglePlayer,
    confirmEscalate,
    recordClip,
  }), [
    state,
    applyState, markSafe, openModal, closeModal,
    toggleMute, toggleWhy, dismissAlert, setFilter,
    setSearch, togglePlayer, confirmEscalate, recordClip,
  ])

  return (
    <MonitorContext.Provider value={value}>
      {children}
    </MonitorContext.Provider>
  )
}
