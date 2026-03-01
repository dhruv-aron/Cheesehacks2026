import { useMonitor } from '../context/MonitorContext.jsx'

const SCREENS = [
  { key: 'normal',       label: 'Normal'       },
  { key: 'elevated',     label: 'Elevated'     },
  { key: 'high',         label: 'High Threat'  },
  { key: 'reconnecting', label: 'Reconnecting' },
]

export default function DemoSwitcher() {
  const { currentStateName, applyState } = useMonitor()

  return (
    <nav className="demo-bar" aria-label="Demo state switcher">
      <span className="demo-lbl">SCREEN</span>
      {SCREENS.map(s => (
        <button
          key={s.key}
          className={`demo-btn${currentStateName === s.key ? ' on' : ''}`}
          onClick={() => applyState(s.key)}
        >
          {s.label}
        </button>
      ))}
    </nav>
  )
}
