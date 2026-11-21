import { useEffect, useState } from 'react'
import { MessageSquare, Orbit, Workflow, Gauge, Columns3, Sun, Moon } from 'lucide-react'
import Chat from './tabs/Chat'
import GraphTab from './tabs/GraphTab'
import WorkflowTab from './tabs/WorkflowTab'
import Dashboard from './tabs/Dashboard'
import Compare from './tabs/Compare'
import ErrorBoundary from './components/ErrorBoundary'

const TABS = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'graph', label: 'Knowledge Graph', icon: Orbit },
  { id: 'workflow', label: 'Workflow', icon: Workflow },
  { id: 'kpi', label: 'Telemetry', icon: Gauge },
  { id: 'compare', label: 'Benchmark', icon: Columns3 },
] as const

export type Toggles = { nodes: Record<string, boolean>; edges: Record<string, boolean> }
export type Shared = {
  toggles: Record<string, Toggles>   // keyed by engine id
  setToggles: (engine: string, t: Toggles) => void
  excludedNodes: string[]; setExcludedNodes: (x: string[]) => void
  excludedEdges: string[]; setExcludedEdges: (x: string[]) => void
  goto: (t: string) => void
}

export default function App() {
  const [tab, setTab] = useState<string>('chat')
  const [dark, setDark] = useState(() => (localStorage.getItem('theme') ?? 'dark') === 'dark')
  const [toggles, setToggleMap] = useState<Shared['toggles']>({})
  const setToggles = (engine: string, t: Toggles) => setToggleMap(m => ({ ...m, [engine]: t }))
  const [excludedNodes, setExcludedNodes] = useState<string[]>([])
  const [excludedEdges, setExcludedEdges] = useState<string[]>([])
  const [messages, setMessages] = useState<any[]>([])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  const shared: Shared = { toggles, setToggles, excludedNodes, setExcludedNodes, excludedEdges, setExcludedEdges, goto: setTab }

  return (
    <div className="h-full flex flex-col">
      <header className="h-14 shrink-0 flex items-center justify-between px-5 border-b border-line/70">
        <div className="flex items-center gap-2.5 w-56">
          <div className="w-6 h-6 rounded-md bg-accent text-accentfg grid place-items-center text-[11px] font-bold">P</div>
          <span className="text-[13.5px] font-semibold tracking-tight">TriRAG Advisor <span className="text-muted font-normal">· PwC India</span></span>
        </div>
        <nav className="flex gap-1 p-1 rounded-full border border-line bg-panel">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[12.5px] font-medium transition-all ${tab === t.id ? 'bg-accent text-accentfg' : 'text-muted hover:text-fg'}`}>
              <t.icon size={14} /><span className="hidden md:inline">{t.label}</span>
            </button>
          ))}
        </nav>
        <div className="w-56 flex justify-end">
          <button className="btn !p-2" onClick={() => setDark(!dark)} title="Toggle theme">{dark ? <Sun size={15} /> : <Moon size={15} />}</button>
        </div>
      </header>
      <main className="flex-1 min-h-0 relative">
        {/* Chat stays mounted so the conversation survives tab switches */}
        <div className={tab === 'chat' ? 'h-full' : 'hidden'}><ErrorBoundary label="Chat"><Chat shared={shared} messages={messages} setMessages={setMessages} /></ErrorBoundary></div>
        {tab === 'graph' && <ErrorBoundary label="Knowledge graph" resetKey={dark}><GraphTab shared={shared} dark={dark} /></ErrorBoundary>}
        {tab === 'workflow' && <ErrorBoundary label="Workflow"><WorkflowTab shared={shared} /></ErrorBoundary>}
        {tab === 'kpi' && <ErrorBoundary label="Telemetry"><Dashboard /></ErrorBoundary>}
        {tab === 'compare' && <ErrorBoundary label="Benchmark"><Compare /></ErrorBoundary>}
      </main>
    </div>
  )
}
