import { useEffect, useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, Handle, Position, MarkerType, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Play, RotateCcw, Loader2, Lock } from 'lucide-react'
import { api } from '../api'
import Markdown from '../components/Markdown'
import type { Shared } from '../App'

function StepNode({ data }: NodeProps) {
  const d = data as any
  return (
    <div onClick={d.onToggle} className={`w-52 card p-3.5 cursor-pointer transition-all select-none ${d.on ? '' : 'opacity-40 border-dashed'} ${d.trace && !d.trace.skipped ? '!border-good/60' : ''}`}>
      <Handle type="target" position={Position.Left} className="!bg-muted !w-1.5 !h-1.5 !border-0" />
      <Handle type="source" position={Position.Right} className="!bg-muted !w-1.5 !h-1.5 !border-0" />
      <Handle id="b-out" type="source" position={Position.Bottom} className="!bg-muted !w-1.5 !h-1.5 !border-0" style={{ left: '70%' }} />
      <Handle id="b-in" type="target" position={Position.Bottom} className="!bg-muted !w-1.5 !h-1.5 !border-0" style={{ left: '30%' }} />
      <div className="flex items-center justify-between mb-1">
        <span className="label !text-[10px]">Step {d.idx}</span>
        {d.locked ? <Lock size={11} className="text-muted" /> : <span className={`w-7 h-4 rounded-full relative transition-colors ${d.on ? 'bg-good' : 'bg-line'}`}><i className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${d.on ? 'left-3.5' : 'left-0.5'}`} /></span>}
      </div>
      <div className="text-[13.5px] font-semibold leading-tight">{d.label}</div>
      <div className="text-[11px] text-muted mt-1.5 leading-snug">{d.desc}</div>
      {d.trace && <div className="mt-2 pt-2 border-t border-line text-[11px] text-muted"><b className="text-fg">{d.trace.ms} ms</b>{d.trace.detail ? ` · ${d.trace.detail}` : ''}</div>}
    </div>
  )
}
const nodeTypes = { step: StepNode }

export default function WorkflowTab({ shared }: { shared: Shared }) {
  const [wf, setWf] = useState<any>(null)
  const [q, setQ] = useState('Which ISD-related tax exposure does the Seller indemnity cover, and what interest rate applies?')
  const [area, setArea] = useState('deals')
  const [run, setRun] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const { nodes: nOn, edges: eOn } = shared.toggles
  useEffect(() => { api.workflow().then(setWf) }, [])

  const setNode = (id: string) => shared.setToggles({ nodes: { ...nOn, [id]: !(nOn[id] ?? true) }, edges: eOn })
  const setEdge = (id: string) => shared.setToggles({ nodes: nOn, edges: { ...eOn, [id]: !(eOn[id] ?? true) } })

  const trace: Record<string, any> = useMemo(() => Object.fromEntries((run?.trace ?? []).map((t: any) => [t.node, t])), [run])
  const nodes = useMemo(() => (wf?.nodes ?? []).map((n: any, i: number) => ({
    id: n.id, type: 'step', position: { x: i * 270, y: 60 }, draggable: false,
    data: { ...n, idx: i + 1, on: n.id === 'synthesis' ? true : (nOn[n.id] ?? true), locked: n.id === 'synthesis', trace: trace[n.id], onToggle: () => n.id !== 'synthesis' && setNode(n.id) },
  })), [wf, nOn, trace])
  const edges = useMemo(() => (wf?.edges ?? []).map((e: any) => {
    const on = eOn[e.id] ?? true
    return { id: e.id, source: e.source, target: e.target, animated: on, type: e.loop ? 'default' : 'smoothstep',
      ...(e.loop ? { sourceHandle: 'b-out', targetHandle: 'b-in', label: 'no graph hits → re-seed', labelStyle: { fontSize: 10, fill: 'var(--muted)' }, labelBgStyle: { fill: 'var(--bg)' } } : {}),
      style: { stroke: on ? 'var(--fg)' : 'var(--line)', strokeWidth: on ? 1.5 : 1.2, strokeDasharray: on ? undefined : '5 5', cursor: 'pointer' },
      markerEnd: { type: MarkerType.ArrowClosed, color: on ? 'var(--fg)' : 'var(--line)' }, interactionWidth: 24 }
  }), [wf, eOn])

  const exec = async () => {
    setBusy(true); setErr(''); setRun(null)
    try { setRun(await api.chat({ message: q, engine: 'graph', practice_area: area, toggles: shared.toggles, excluded_nodes: shared.excludedNodes, excluded_edges: shared.excludedEdges, evaluate: false })) }
    catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const anyOff = Object.values(nOn).includes(false) || Object.values(eOn).includes(false)

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-4 pb-2 flex items-end justify-between">
        <div><div className="text-[15px] font-semibold">LangGraph workflow</div>
          <div className="text-xs text-muted mt-0.5">Click a node or edge to toggle it. Disabled nodes pass state through; a disabled edge bypasses the node it feeds. Changes also apply to Graph RAG chats.</div></div>
        <button className="btn" disabled={!anyOff} onClick={() => shared.setToggles({ nodes: {}, edges: {} })}><RotateCcw size={13} />Reset</button>
      </div>
      <div className="flex-1 min-h-[280px]">
        {wf && <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onInit={i => setTimeout(() => i.fitView({ padding: 0.12 }), 60)} nodesConnectable={false}
          onEdgeClick={(_, e) => setEdge(e.id)} proOptions={{ hideAttribution: true }} minZoom={0.4}>
          <Background gap={22} size={1} color="var(--line)" /><Controls showInteractive={false} />
        </ReactFlow>}
      </div>
      <div className="border-t border-line/70 p-5 grid md:grid-cols-[1fr_1.4fr] gap-5 max-h-[42%] overflow-y-auto">
        <div className="space-y-3">
          <div className="label">Test this pipeline variant</div>
          <textarea value={q} onChange={e => setQ(e.target.value)} rows={3} className="w-full card p-3 text-sm bg-transparent outline-none resize-none" />
          <div className="flex gap-2 items-center">
            <select className="pill-select" value={area} onChange={e => setArea(e.target.value)}>
              <option value="tax">Tax & Regulatory</option><option value="grc">Risk Advisory & GRC</option><option value="deals">Deal Advisory</option></select>
            <button className="btn btn-primary ml-auto" disabled={busy || !q.trim()} onClick={exec}>{busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}Run</button>
          </div>
          {err && <div className="text-xs text-bad">{err}</div>}
        </div>
        <div className="text-sm min-w-0">
          {run ? <>
            <div className="flex flex-wrap gap-2 mb-3 text-[11.5px] text-muted">
              <span className="border border-line rounded-full px-2.5 py-1">Total {(run.timings.total_ms / 1000).toFixed(1)}s</span>
              <span className="border border-line rounded-full px-2.5 py-1">{run.sources.length} sources</span>
              {run.seeds?.length > 0 && <span className="border border-line rounded-full px-2.5 py-1">seeds: {run.seeds.join(', ')}</span>}
              {run.trace.filter((t: any) => t.node === 'loop').map((_: any, i: number) => <span key={i} className="border border-warn/40 text-warn rounded-full px-2.5 py-1">cycle taken</span>)}
            </div>
            <div className="max-h-52 overflow-y-auto pr-2"><Markdown text={run.answer} /></div></>
            : <div className="text-muted text-xs h-full grid place-items-center">Run a query to see per-node timings on the canvas.</div>}
        </div>
      </div>
    </div>
  )
}
