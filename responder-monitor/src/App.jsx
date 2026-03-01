import { useEffect } from 'react'
import { MonitorProvider, useMonitor } from './context/MonitorContext.jsx'
import TopBar       from './components/TopBar.jsx'
import AlertBanner  from './components/AlertBanner.jsx'
import PlayerColumn from './components/PlayerColumn.jsx'
import Sidebar      from './components/Sidebar.jsx'
import EscalateModal from './components/EscalateModal.jsx'
import DemoSwitcher from './components/DemoSwitcher.jsx'

function MonitorApp() {
  const { openModal, markSafe, closeModal, modalOpen } = useMonitor()

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.target.matches('input, textarea, select')) return
      if (e.key === 'e' || e.key === 'E') { if (!modalOpen) openModal() }
      if (e.key === 's' || e.key === 'S') markSafe()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [openModal, markSafe, modalOpen])

  return (
    <>
      <TopBar />
      <AlertBanner />
      <main className="main" role="main">
        <PlayerColumn />
        <Sidebar />
      </main>
      <EscalateModal />
      <DemoSwitcher />
    </>
  )
}

export default function App() {
  return (
    <MonitorProvider>
      <MonitorApp />
    </MonitorProvider>
  )
}
