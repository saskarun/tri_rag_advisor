import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import SpriteText from 'three-spritetext'
import { RotateCcw, Network } from 'lucide-react'
import { api } from '../api'
import SphereCanvas from '../components/SphereCanvas'
import type { Shared } from '../App'

const TYPE_COLORS: Record<string, string> = {
  Authority: '#60a5fa', Law: '#a78bfa', Organization: '#34d399', Obligation: '#fbbf24',
  Control: '#f472b6', Penalty: '#f87171', Threshold: '#2dd4bf', Concept: '#9ca3af',
}
const R = 150

function hasWebGL() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')) } catch { return false }
}

export default function GraphTab({ shared, dark }: { shared: Shared; dark: boolean }) {
  const [data, setData] = useState<any>(null)
  const [sel, setSel] = useState<any>(null)
  const [size, setSize] = useState({ w: 800, h: 600 })
  const wrap = useRef<HTMLDivElement>(null)
  const fg = useRef<any>(null)
  const interacting = useRef(false)
  const webgl = useMemo(hasWebGL, [])
  const exN = new Set(shared.excludedNodes), exE = new Set(shared.excludedEdges)

  useEffect(() => { api.graph().then(setData) }, [])
  useEffect(() => {
    const el = wrap.current; if (!el) return
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight })); ro.observe(el); return () => ro.disconnect()
  }, [])

  // place every entity on a sphere (Fibonacci lattice); highest-degree nodes first
  const graph = useMemo(() => {
    if (!data) return { nodes: [], links: [] }
    const ns = [...data.nodes].sort((a: any, b: any) => b.degree - a.degree), n = ns.length
    const nodes = ns.map((d: any, i: number) => {
      const y = n === 1 ? 0 : 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), th = Math.PI * (3 - Math.sqrt(5)) * i
      return { ...d, fx: R * r * Math.cos(th), fy: R * y, fz: R * r * Math.sin(th) }
    })
    return { nodes, links: data.edges.map((e: any) => ({ ...e })) }
  }, [data])

  useEffect(() => { // slow orbit until the user grabs the canvas
    let a = 0
    const t = setInterval(() => {
      if (!webgl || interacting.current || !fg.current) return
      a += 0.004; fg.current.cameraPosition({ x: 380 * Math.sin(a), y: 60, z: 380 * Math.cos(a) })
    }, 30)
    return () => clearInterval(t)
  }, [graph])

  const toggleNode = (id: string) => shared.setExcludedNodes(exN.has(id) ? shared.excludedNodes.filter(x => x !== id) : [...shared.excludedNodes, id])
  const toggleEdge = (id: string) => shared.setExcludedEdges(exE.has(id) ? shared.excludedEdges.filter(x => x !== id) : [...shared.excludedEdges, id])
  const active = graph.nodes.length - exN.size
  const label = dark ? '#ededee' : '#111'

  return (
    <div className="h-full flex">
      <div ref={wrap} className="flex-1 relative min-w-0" onPointerDown={() => (interacting.current = true)}>
        {graph.nodes.length === 0
          ? <div className="h-full grid place-items-center text-muted text-sm"><div className="text-center"><Network className="mx-auto mb-3" />No graph yet — load documents in the Chat tab.</div></div>
          : !webgl ? <SphereCanvas nodes={graph.nodes} links={graph.links} colors={TYPE_COLORS} exN={exN} exE={exE} dark={dark}
              onNode={(n: any) => { toggleNode(n.id); setSel(n) }} onLink={(l: any) => toggleEdge(l.id)} />
          : <ForceGraph3D ref={fg} width={size.w} height={size.h} graphData={graph} backgroundColor="rgba(0,0,0,0)" showNavInfo={false}
              cooldownTicks={0} enableNodeDrag={false}
              nodeLabel={(n: any) => `${n.id} · ${n.type}`} nodeRelSize={5}
              nodeVal={(n: any) => 1 + Math.min(n.degree, 6) * 0.6}
              nodeColor={(n: any) => exN.has(n.id) ? (dark ? '#3a3a40' : '#cfcfd4') : TYPE_COLORS[n.type] ?? '#9ca3af'}
              nodeOpacity={0.95}
              nodeThreeObjectExtend nodeThreeObject={(n: any) => {
                const s = new SpriteText(n.id.length > 26 ? n.id.slice(0, 24) + '…' : n.id)
                s.color = exN.has(n.id) ? (dark ? '#55555c' : '#b5b5bb') : label; s.textHeight = 3.6; s.position.y = 9; (s.material as any).depthWrite = false
                return s
              }}
              linkColor={(l: any) => exE.has(l.id) ? (dark ? '#2a2a2e' : '#e0e0e4') : (dark ? '#6b6b75' : '#9a9aa4')}
              linkWidth={(l: any) => exE.has(l.id) ? 0.2 : 0.8} linkOpacity={0.55} linkCurvature={0.28}
              linkDirectionalArrowLength={3} linkDirectionalArrowRelPos={0.92}
              linkLabel={(l: any) => l.relation}
              onNodeClick={(n: any) => { toggleNode(n.id); setSel(n) }}
              onLinkClick={(l: any) => toggleEdge(l.id)} />}
        <div className="absolute left-5 top-4 pointer-events-none">
          <div className="text-[15px] font-semibold">Knowledge graph</div>
          <div className="text-xs text-muted mt-0.5">Click a node or edge to exclude it from Graph RAG retrieval. Drag to rotate.</div>
          {!webgl && <div className="text-[11px] text-warn mt-1">WebGL unavailable in this browser — showing the software-rendered sphere view.</div>}
        </div>
      </div>

      <aside className="w-80 shrink-0 border-l border-line/70 p-5 overflow-y-auto space-y-5">
        <div className="grid grid-cols-3 gap-2 text-center">
          {[['Nodes', `${active}/${graph.nodes.length}`], ['Edges', `${graph.links.length - exE.size}/${graph.links.length}`], ['Filters', exN.size + exE.size]].map(([k, v]) =>
            <div key={k as string} className="card !rounded-xl py-2.5"><div className="text-base font-semibold">{v}</div><div className="label !text-[10px]">{k}</div></div>)}
        </div>
        <button className="btn w-full justify-center" disabled={!exN.size && !exE.size} onClick={() => { shared.setExcludedNodes([]); shared.setExcludedEdges([]) }}><RotateCcw size={13} />Select all</button>

        <div>
          <div className="label mb-2">Entity types</div>
          <div className="grid grid-cols-2 gap-1.5 text-xs">
            {Object.entries(TYPE_COLORS).map(([t, c]) => <div key={t} className="flex items-center gap-2 text-muted"><span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />{t}</div>)}
          </div>
        </div>

        {sel && <div className="card p-4 text-sm">
          <div className="label mb-1">{sel.type}</div>
          <div className="font-medium mb-2">{sel.id}</div>
          {sel.aliases?.length > 1 && <div className="text-xs text-muted mb-2"><b className="text-fg/80">Aliases merged:</b> {sel.aliases.join(' · ')}</div>}
          <div className="text-xs text-muted mb-2"><b className="text-fg/80">Documents:</b> {sel.docs?.join(', ')}</div>
          <div className="text-xs text-muted"><b className="text-fg/80">Connections:</b> {graph.links.filter((l: any) => (l.source.id ?? l.source) === sel.id || (l.target.id ?? l.target) === sel.id)
            .map((l: any) => { const s = l.source.id ?? l.source, t = l.target.id ?? l.target; return s === sel.id ? `${l.relation} → ${t}` : `${s} → ${l.relation}` }).slice(0, 8).join('; ')}</div>
          <div className={`mt-3 text-xs ${exN.has(sel.id) ? 'text-warn' : 'text-good'}`}>{exN.has(sel.id) ? 'Excluded from retrieval' : 'Included in retrieval'}</div>
        </div>}
        <p className="text-[11.5px] text-muted leading-relaxed">Filters apply to the Graph RAG engine only: excluded entities and relations are skipped during k-hop traversal.</p>
      </aside>
    </div>
  )
}
