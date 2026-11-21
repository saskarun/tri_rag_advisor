import { useEffect, useState } from 'react'
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis } from 'recharts'
import { RefreshCw, Check, Loader2 } from 'lucide-react'
import { api, ENGINES } from '../api'

const HP = [
  { key: 'chunk_size', label: 'Chunk size', unit: 'tokens', min: 100, max: 600, step: 20, note: 'Re-index required. Effective size is capped at 510 by the bge 512-token limit.' },
  { key: 'chunk_overlap', label: 'Chunk overlap', unit: 'tokens', min: 0, max: 200, step: 10, note: 'Re-index required.' },
  { key: 'hyde_n', label: 'Multi-HyDE passages (N)', unit: 'docs', min: 1, max: 6, step: 1, note: 'Synthetic documents per query.' },
  { key: 'hop_radius', label: 'Graph hop radius (k)', unit: 'hops', min: 1, max: 4, step: 1, note: 'Entity-relation expansion depth.' },
  { key: 'rrf_alpha', label: 'RRF constant (α)', unit: '', min: 1, max: 120, step: 1, note: 'Fuses BM25, vector and graph ranks.' },
  { key: 'top_k', label: 'Context chunks (top-k)', unit: 'chunks', min: 1, max: 10, step: 1, note: 'Chunks sent to the LLM.' },
]
const avg = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null)

export default function Dashboard() {
  const [k, setK] = useState<any>(null)
  const [hp, setHp] = useState<Record<string, number>>({})
  const [dirty, setDirty] = useState(false)
  const [needReindex, setNeedReindex] = useState(false)
  const [busy, setBusy] = useState('')
  const [engine, setEngine] = useState('graph')
  const [err, setErr] = useState('')

  const load = () => api.kpis().then(d => { setK(d); setHp(h => (dirty ? h : d.hyperparams)) }).catch(() => {})
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t) }, [dirty])

  const apply = async () => {
    setErr('')
    try { const r = await api.setConfig(hp); setDirty(false); setNeedReindex(r.needs_reindex) } catch (e: any) { setErr(e.message) }
  }
  const reindex = async () => { setBusy('Re-indexing…'); try { await api.reindex(); setNeedReindex(false) } finally { setBusy('') } }

  if (!k) return <div className="p-8 text-muted text-sm">Loading…</div>
  const recent = (k.recent as any[]).filter(r => r.engine === engine)
  const bm = k.benchmark?.[engine]
  const lat = avg(recent.map(r => r.timings.total_ms))
  const parts = recent.length ? {
    retrieval: avg(recent.map(r => r.timings.retrieval_ms))!, graph: avg(recent.map(r => r.timings.graph_ms))!, llm: avg(recent.map(r => r.timings.llm_ms))!,
  } : bm ? { retrieval: bm.latency.retrieval_ms, graph: bm.latency.graph_ms, llm: bm.latency.llm_ms } : null
  const total = parts ? parts.retrieval + parts.graph + parts.llm : 0
  const faith = avg(recent.map(r => r.faithfulness).filter((x: any) => x != null)) ?? bm?.faithfulness ?? null
  const spark = recent.map((r, i) => ({ i, ms: r.timings.total_ms }))

  const Card = ({ title, value, sub, children }: any) => (
    <div className="card p-5 flex flex-col gap-1">
      <div className="label">{title}</div>
      <div className="text-[32px] font-semibold tracking-tight leading-tight">{value}</div>
      <div className="text-xs text-muted">{sub}</div>{children}
    </div>)

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-8">
        <div className="flex items-end justify-between">
          <div><h2 className="text-xl font-semibold">Telemetry</h2><p className="text-sm text-muted mt-1">Live hyperparameters and KPIs. Chat runs feed latency & faithfulness; the benchmark feeds recall.</p></div>
          <div className="flex gap-1 p-1 rounded-full border border-line bg-panel">
            {ENGINES.map(e => <button key={e.id} onClick={() => setEngine(e.id)} className={`px-3.5 py-1.5 rounded-full text-xs font-medium ${engine === e.id ? 'bg-accent text-accentfg' : 'text-muted hover:text-fg'}`}>{e.short}</button>)}
          </div>
        </div>

        <section>
          <div className="label mb-3">Core KPIs · {ENGINES.find(e => e.id === engine)?.label}</div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card title="Retrieval context recall" value={bm ? `${(bm.rcr * 100).toFixed(0)}%` : '—'} sub={bm ? 'Ground-truth facts found in retrieved chunks' : 'Run the benchmark to measure'} />
            <Card title="Faithfulness" value={faith != null ? faith.toFixed(2) : '—'} sub={faith != null ? `${(1 - faith).toFixed(2)} hallucination · LLM-judged, 0–1` : 'Ask a question to measure'} />
            <Card title="Entity-relation accuracy" value={k.entity_resolution?.score != null ? `${(k.entity_resolution.score * 100).toFixed(0)}%` : '—'}
              sub={k.entity_resolution?.score != null ? `${k.entity_resolution.correct}/${k.entity_resolution.checked} gold links resolved${engine !== 'graph' ? ' (graph index)' : ''}` : 'Index documents first'} />
            <Card title="End-to-end latency" value={lat != null ? `${Math.round(lat)} ms` : bm ? `${bm.latency.total_ms} ms` : '—'} sub={recent.length ? `avg of last ${recent.length} chat run(s)` : bm ? 'benchmark average' : 'Ask a question to measure'}>
              {parts && total > 0 && <div className="mt-3">
                <div className="flex h-2 rounded-full overflow-hidden bg-panel2">
                  <i style={{ width: `${(parts.retrieval / total) * 100}%`, background: '#60a5fa' }} /><i style={{ width: `${(parts.graph / total) * 100}%`, background: '#a78bfa' }} /><i style={{ width: `${(parts.llm / total) * 100}%`, background: 'var(--muted)' }} />
                </div>
                <div className="flex justify-between text-[10.5px] text-muted mt-1.5"><span>● retrieval {Math.round(parts.retrieval)}</span><span>● graph {Math.round(parts.graph)}</span><span>● LLM {Math.round(parts.llm)}</span></div></div>}
            </Card>
          </div>
          {spark.length > 1 && <div className="card mt-4 p-4"><div className="label mb-2">Latency per chat run (ms)</div>
            <div className="h-24"><ResponsiveContainer><LineChart data={spark}><YAxis hide domain={['dataMin - 500', 'dataMax + 500']} />
              <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10, fontSize: 12 }} formatter={(v: any) => [`${v} ms`, 'latency']} labelFormatter={() => ''} />
              <Line dataKey="ms" stroke="var(--fg)" strokeWidth={1.8} dot={false} /></LineChart></ResponsiveContainer></div></div>}
        </section>

        <section>
          <div className="flex items-center justify-between mb-3">
            <div className="label">Hyperparameters</div>
            <div className="flex items-center gap-2">
              {err && <span className="text-xs text-bad">{err}</span>}
              {needReindex && <button className="btn" onClick={reindex} disabled={!!busy}>{busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}{busy || 'Re-index with new chunking'}</button>}
              <button className="btn btn-primary" disabled={!dirty} onClick={apply}><Check size={13} />Apply</button>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {HP.map((h, i) => (
              <div key={h.key} className={`card p-4 ${i >= 4 ? 'opacity-80' : ''}`}>
                <div className="flex items-baseline justify-between"><span className="text-[13px] font-medium">{h.label}</span>
                  <span className="font-mono text-lg font-medium">{hp[h.key]}<span className="text-xs text-muted ml-1">{h.unit}</span></span></div>
                <input type="range" className="w-full mt-3" min={h.min} max={h.max} step={h.step} value={hp[h.key] ?? 0}
                  onChange={e => { setHp({ ...hp, [h.key]: Number(e.target.value) }); setDirty(true) }} />
                <div className="text-[11px] text-muted mt-1.5">{h.note}</div>
              </div>))}
          </div>
        </section>

        {k.index?.chunks != null && <section>
          <div className="label mb-3">Index</div>
          <div className="card p-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
            {[['Documents', k.index.documents], ['Chunks', k.index.chunks], ['Graph nodes', k.index.nodes], ['Graph edges', k.index.edges], ['Embedding', k.index.embed_model?.split('/').pop()]].map(([a, b]) => <div key={a as string}><span className="text-muted">{a} </span><b>{b}</b></div>)}
            {k.index.timings_ms && <div className="text-muted text-xs w-full">Last build (ms): {Object.entries(k.index.timings_ms).map(([a, b]) => `${a.replace('_ms', '')} ${b}`).join(' · ')}</div>}
          </div>
        </section>}
      </div>
    </div>
  )
}
