import { useEffect, useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, Handle, Position, MarkerType, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Play, RotateCcw, Loader2, Lock } from 'lucide-react'
import { api, ENGINES } from '../api'
import Markdown from '../components/Markdown'
import type { Shared } from '../App'

function StepNode({ data }: NodeProps) {
  const d = data as any
  return (
    <div onClick={d.onToggle} className={`w-52 card p-3.5 select-none transition-all ${d.locked ? '' : 'cursor-pointer'} ${d.on ? '' : 'opacity-40 border-dashed'} ${d.trace && !d.trace.skipped ? '!border-good/60' : ''}`}>
      <Handle type="target" position={Position.Left} className="!bg-muted !w-1.5 !h-1.5 !border-0" />
      <Handle type="source" position={Position.Right} className="!bg-muted !w-1.5 !h-1.5 !border-0" />
      <Handle id="b-out" type="source" position={Position.Bottom} className="!bg-muted !w-1.5 !h-1.5 !border-0" style={{ left: '70%' }} />
      <Handle id="b-in" type="target" position={Position.Bottom} className="!bg-muted !w-1.5 !h-1.5 !border-0" style={{ left: '30%' }} />
      <div className="flex items-center justify-between mb-1">
        <span className="label !text-[10px]">Step {d.idx}{d.parallel ? ' · parallel' : ''}</span>
        {d.locked ? <Lock size={11} className="text-muted" /> : <span className={`w-7 h-4 rounded-full relative transition-colors ${d.on ? 'bg-good' : 'bg-line'}`}><i className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${d.on ? 'left-3.5' : 'left-0.5'}`} /></span>}
      </div>
      <div className="text-[13.5px] font-semibold leading-tight">{d.label}</div>
      <div className="text-[11px] text-muted mt-1.5 leading-snug">{d.desc}</div>
      {d.trace && <div className="mt-2 pt-2 border-t border-line text-[11px] text-muted"><b className="text-fg">{d.trace.ms} ms</b>{d.trace.detail ? ` · ${d.trace.detail}` : ''}</div>}
    </div>
  )
}
const nodeTypes = { step: StepNode }

const DEFAULT_Q: Record<string, string> = {
  standard: 'What is the turnover threshold for mandatory e-invoicing under Rule 48(4)?',
  hyde: 'What is the cut-off ownership stake that triggers identification of the real controllers of a corporate customer?',
  graph: 'Which ISD-related tax exposure does the Seller indemnity cover, and what interest rate applies?',
}

export default function WorkflowTab({ shared }: { shared: Shared }) {
  const engine = shared.wfEngine, setEngine = shared.setWfEngine
  const [wf, setWf] = useState<any>(null)
  const [qs, setQs] = useState<Record<string, string>>(DEFAULT_Q)
  const [area, setArea] = useState('deals')
  const [run, setRun] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const tg = shared.toggles[engine] ?? { nodes: {}, edges: {} }
  const { nodes: nOn, edges: eOn } = tg

  useEffect(() => { setWf(null); setRun(null); setErr(''); api.workflow(engine).then(setWf).catch(e => setErr(e.message)) }, [engine])

  const setNode = (id: string) => shared.setToggles(engine, { nodes: { ...nOn, [id]: !(nOn[id] ?? true) }, edges: eOn })
  const setEdge = (id: string) => shared.setToggles(engine, { nodes: nOn, edges: { ...eOn, [id]: !(eOn[id] ?? true) } })
  const toggleable = (wf?.nodes ?? []).some((n: any) => !n.locked)

  const trace: Record<string, any> = useMemo(() => Object.fromEntries((run?.trace ?? []).map((t: any) => [t.node, t])), [run])
  const nodes = useMemo(() => (wf?.nodes ?? []).map((n: any, i: number) => ({
    id: n.id, type: 'step', position: { x: (n.col ?? i) * 270, y: n.row != null ? n.row * 190 : 60 }, draggable: false,
    data: { ...n, idx: (n.col ?? i) + 1, parallel: (wf.nodes as any[]).filter((m: any) => m.col === n.col).length > 1, on: n.locked ? true : (nOn[n.id] ?? true), trace: trace[n.id], onToggle: () => !n.locked && setNode(n.id) },
  })), [wf, nOn, trace])
  const edges = useMemo(() => (wf?.edges ?? []).map((e: any) => {
    const on = eOn[e.id] ?? true
    return { id: e.id, source: e.source, target: e.target, animated: on, type: e.loop ? 'default' : 'smoothstep',
      ...(e.loop ? { sourceHandle: 'b-out', targetHandle: 'b-in', label: 'no graph hits → re-seed', labelStyle: { fontSize: 10, fill: 'var(--muted)' }, labelBgStyle: { fill: 'var(--bg)' } } : {}),
      style: { stroke: on ? 'var(--fg)' : 'var(--line)', strokeWidth: on ? 1.5 : 1.2, strokeDasharray: on ? undefined : '5 5', cursor: toggleable ? 'pointer' : 'default' },
      markerEnd: { type: MarkerType.ArrowClosed, color: on ? 'var(--fg)' : 'var(--line)' }, interactionWidth: 24 }
  }), [wf, eOn, toggleable])

  const exec = async () => {
    setBusy(true); setErr(''); setRun(null)
    try {
      setRun(await api.chat({ message: qs[engine], engine, practice_area: area, toggles: tg,
        excluded_nodes: engine === 'graph' ? shared.excludedNodes : [], excluded_edges: engine === 'graph' ? shared.excludedEdges : [], evaluate: false }))
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const anyOff = Object.values(nOn).includes(false) || Object.values(eOn).includes(false)
  const eng = ENGINES.find(e => e.id === engine)!

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-4 pb-2 flex items-center justify-between gap-4">
        <div className="flex gap-1 p-1 rounded-full border border-line bg-panel">
          {ENGINES.map(e => (
            <button key={e.id} onClick={() => setEngine(e.id)}
              className={`px-4 py-1.5 rounded-full text-[12.5px] font-medium transition-all ${engine === e.id ? 'bg-accent text-accentfg' : 'text-muted hover:text-fg'}`}>{e.label}</button>))}
        </div>
        <button className="btn" disabled={!anyOff} onClick={() => shared.setToggles(engine, { nodes: {}, edges: {} })}><RotateCcw size={13} />Reset {eng.short}</button>
      </div>
      <div className="px-6 pb-1">
        <div className="text-[15px] font-semibold">{eng.label} workflow</div>
        <div className="text-xs text-muted mt-0.5 max-w-3xl">
          {wf?.blurb} {toggleable && 'Click a node or edge to toggle it: a disabled node passes state through, and a disabled edge bypasses the node it feeds. Changes also apply to this engine in Chat.'}
          {wf && !toggleable && ' Locked steps (padlock) always run.'}
        </div>
      </div>
      <div className="flex-1 min-h-[260px]">
        {wf && <ReactFlow key={engine} nodes={nodes} edges={edges} nodeTypes={nodeTypes} nodesConnectable={false}
          fitView fitViewOptions={{ padding: 0.12, maxZoom: 1 }} onInit={i => { setTimeout(() => i.fitView({ padding: 0.12, maxZoom: 1 }), 120); setTimeout(() => i.fitView({ padding: 0.12, maxZoom: 1 }), 450) }}
          onEdgeClick={(_, e) => toggleable && setEdge(e.id)} proOptions={{ hideAttribution: true }} minZoom={0.4}>
          <Background gap={22} size={1} color="var(--line)" /><Controls showInteractive={false} />
        </ReactFlow>}
      </div>
      <div className="border-t border-line/70 p-5 grid md:grid-cols-[1fr_1.4fr] gap-5 max-h-[42%] overflow-y-auto">
        <div className="space-y-3">
          <div className="label">Test this {eng.short} variant</div>
          <textarea value={qs[engine]} onChange={e => setQs({ ...qs, [engine]: e.target.value })} rows={3} className="w-full card p-3 text-sm bg-transparent outline-none resize-none" />
          <div className="flex gap-2 items-center">
            <select className="pill-select" value={area} onChange={e => setArea(e.target.value)}>
              <option value="tax">Tax & Regulatory</option><option value="grc">Risk Advisory & GRC</option><option value="deals">Deal Advisory</option></select>
            <button className="btn btn-primary ml-auto" disabled={busy || !qs[engine]?.trim()} onClick={exec}>{busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}Run</button>
          </div>
          {err && <div className="text-xs text-bad">{err}</div>}
        </div>
        <div className="text-sm min-w-0">
          {run ? <>
            <div className="flex flex-wrap gap-2 mb-3 text-[11.5px] text-muted">
              <span className="border border-line rounded-full px-2.5 py-1">Total {(run.timings.total_ms / 1000).toFixed(1)}s</span>
              <span className="border border-line rounded-full px-2.5 py-1">{run.sources.length} sources</span>
              {run.hypotheses?.length > 0 && <span className="border border-line rounded-full px-2.5 py-1">{run.hypotheses.length} hypotheses</span>}
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
