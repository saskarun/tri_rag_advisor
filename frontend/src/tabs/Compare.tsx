import { useEffect, useRef, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts'
import { Play, Loader2, Trophy } from 'lucide-react'
import { api, ENGINES, disabledSteps, stepLabel } from '../api'
import type { Shared } from '../App'

const COLORS = { standard: '#9ca3af', hyde: '#60a5fa', graph: '#a78bfa' } as const
const SPEC: [string, string, string, string][] = [
  ['Simple keyword queries', 'High precision / low latency', 'Moderate (HyDE overhead)', 'Moderate (graph overhead)'],
  ['Multi-hop relational queries', 'Poor (misses indirect links)', 'Moderate (semantic expansion)', 'Superior (k-hop edges)'],
  ['Domain vocabulary mismatch', 'Poor (exact vector distance)', 'Superior (synthesizes domain terms)', 'High (entity resolution maps synonyms)'],
  ['Hallucination risk', 'Moderate (out-of-context chunks)', 'Moderate (synthetic drift)', 'Lowest (entity-relation grounding)'],
  ['Best enterprise use case', 'Single-document lookup (SOPs)', 'Vague regulatory inquiries', 'Complex Tax / M&A due diligence'],
]

export default function Compare({ shared }: { shared: Shared }) {
  const [useCustom, setUseCustom] = useState(false)
  const [d, setD] = useState<any>(null)
  const [err, setErr] = useState('')
  const timer = useRef<any>(undefined)
  const load = () => api.bench().then(setD).catch(e => setErr(e.message))
  useEffect(() => { load(); return () => clearInterval(timer.current) }, [])
  useEffect(() => { clearInterval(timer.current); if (d?.state.running) timer.current = setInterval(load, 3000) }, [d?.state.running])

  const customCount = ENGINES.reduce((n, e) => n + disabledSteps(shared.toggles[e.id]).length, 0)
  const customDesc = ENGINES.filter(e => disabledSteps(shared.toggles[e.id]).length).map(e => `${e.short}: ${disabledSteps(shared.toggles[e.id]).map(stepLabel).join(', ')} off`).join(' · ')
  const run = async () => { setErr(''); try { await api.runBench(useCustom ? shared.toggles : undefined); await load() } catch (e: any) { setErr(e.message) } }
  const st = d?.state, res = d?.result, sm = res?.summary
  const pct = st?.total ? Math.round((st.progress / st.total) * 100) : 0

  const best = (vals: (number | null)[], low = false) => {
    const nums = vals.filter((v): v is number => v != null); if (nums.length < 2) return -1
    const t = low ? Math.min(...nums) : Math.max(...nums); return vals.findIndex(v => v === t)
  }
  const rows: { label: string; vals: (number | null)[]; fmt: (v: number) => string; low?: boolean }[] = sm ? [
    { label: 'Retrieval context recall — overall', vals: ENGINES.map(e => sm[e.id].rcr), fmt: v => `${(v * 100).toFixed(0)}%` },
    { label: '  ↳ keyword queries', vals: ENGINES.map(e => sm[e.id].rcr_by_type.keyword), fmt: v => `${(v * 100).toFixed(0)}%` },
    { label: '  ↳ vocabulary mismatch', vals: ENGINES.map(e => sm[e.id].rcr_by_type.vocabulary), fmt: v => `${(v * 100).toFixed(0)}%` },
    { label: '  ↳ multi-hop relational', vals: ENGINES.map(e => sm[e.id].rcr_by_type.multihop), fmt: v => `${(v * 100).toFixed(0)}%` },
    { label: 'Faithfulness (0–1)', vals: ENGINES.map(e => sm[e.id].faithfulness), fmt: v => v.toFixed(2) },
    { label: 'Entity-relation resolution accuracy', vals: ENGINES.map(e => sm[e.id].entity_resolution), fmt: v => `${(v * 100).toFixed(0)}%` },
    { label: 'Avg end-to-end latency', vals: ENGINES.map(e => sm[e.id].latency.total_ms), fmt: v => `${v.toLocaleString()} ms`, low: true },
    { label: '  ↳ retrieval', vals: ENGINES.map(e => sm[e.id].latency.retrieval_ms), fmt: v => `${v} ms`, low: true },
    { label: '  ↳ graph traversal', vals: ENGINES.map(e => sm[e.id].latency.graph_ms), fmt: v => `${v} ms`, low: true },
    { label: '  ↳ LLM inference', vals: ENGINES.map(e => sm[e.id].latency.llm_ms), fmt: v => `${v} ms`, low: true },
  ] : []

  const recallData = sm ? [['keyword', 'Keyword'], ['vocabulary', 'Vocabulary'], ['multihop', 'Multi-hop']].map(([k, l]) => ({ name: l, ...Object.fromEntries(ENGINES.map(e => [e.short, Math.round((sm[e.id].rcr_by_type[k] ?? 0) * 100)])) })) : []
  const latData = sm ? ENGINES.map(e => ({ name: e.short, Retrieval: sm[e.id].latency.retrieval_ms, Graph: sm[e.id].latency.graph_ms, LLM: sm[e.id].latency.llm_ms })) : []
  const tip = { contentStyle: { background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10, fontSize: 12 }, cursor: { fill: 'var(--panel2)' } }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-8">
        <div className="flex items-end justify-between gap-4">
          <div><h2 className="text-xl font-semibold">Comparative benchmark</h2>
            <p className="text-sm text-muted mt-1">{d?.questions?.length ?? 6} golden questions × 3 engines on the currently indexed corpus. Values are measured, not assumed.</p></div>
          <div className="flex items-center gap-3">
            {err && <span className="text-xs text-bad max-w-64">{err}</span>}
            {st?.error && <span className="text-xs text-bad max-w-64">{st.error}</span>}
            {customCount > 0 && <label className="flex items-center gap-2 text-xs text-muted cursor-pointer select-none" title={customDesc}>
              <input type="checkbox" checked={useCustom} onChange={e => setUseCustom(e.target.checked)} disabled={st?.running} />Use my custom pipeline ({customCount} step{customCount > 1 ? 's' : ''} off)</label>}
            <button className="btn btn-primary" onClick={run} disabled={st?.running}>{st?.running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}{st?.running ? `Running ${pct}%` : 'Run benchmark'}</button>
          </div>
        </div>
        {st?.running && <div className="h-1 rounded-full bg-panel2 overflow-hidden"><div className="h-full bg-accent transition-all" style={{ width: `${pct}%` }} /></div>}

        {sm ? <>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="text-left"><th className="p-4 label">Metric</th>{ENGINES.map(e => <th key={e.id} className="p-4 label">{e.label}</th>)}</tr></thead>
              <tbody>{rows.map(r => { const b = best(r.vals, r.low); return (
                <tr key={r.label} className="border-t border-line">
                  <td className={`px-4 py-3 ${r.label.startsWith(' ') ? 'text-muted text-[13px]' : 'font-medium'}`}>{r.label.trim()}</td>
                  {r.vals.map((v, i) => <td key={i} className={`px-4 py-3 font-mono text-[13px] ${v == null ? 'text-muted' : ''}`}>
                    {v == null ? '—' : <span className={`inline-flex items-center gap-1.5 ${b === i ? 'text-good font-semibold' : ''}`}>{r.fmt(v)}{b === i && <Trophy size={11} />}</span>}</td>)}
                </tr>) })}</tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs -mt-5">
            <span className="text-muted">Pipelines benchmarked:</span>
            {ENGINES.map(e => { const off: string[] = res.pipeline?.[e.id] ?? []; return off.length
              ? <span key={e.id} className="border border-warn/40 text-warn rounded-full px-2.5 py-1">{e.short} custom: {off.map(o => '−' + stepLabel(o)).join(' ')}</span>
              : <span key={e.id} className="border border-line text-muted rounded-full px-2.5 py-1">{e.short} default</span> })}
          </div>
          <p className="text-xs text-muted -mt-5">Entity-relation accuracy is a property of the graph index, so it is reported for Graph RAG only. Faithfulness is judged by an LLM and is approximate. Hyperparameters used: {Object.entries(res.hyperparams).map(([a, b]) => `${a}=${b}`).join(', ')}.</p>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="card p-5"><div className="label mb-4">Context recall by query type (%)</div>
              <div className="h-60"><ResponsiveContainer><BarChart data={recallData} barGap={4}><CartesianGrid vertical={false} stroke="var(--line)" /><XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} width={28} /><Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
                {ENGINES.map(e => <Bar key={e.id} dataKey={e.short} fill={COLORS[e.id]} radius={[5, 5, 0, 0]} />)}</BarChart></ResponsiveContainer></div></div>
            <div className="card p-5"><div className="label mb-4">Latency breakdown (ms)</div>
              <div className="h-60"><ResponsiveContainer><BarChart data={latData}><CartesianGrid vertical={false} stroke="var(--line)" /><XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} width={44} /><Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Retrieval" stackId="a" fill="#60a5fa" /><Bar dataKey="Graph" stackId="a" fill="#a78bfa" /><Bar dataKey="LLM" stackId="a" fill="#6b7280" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div></div>
          </div>

          <details className="card p-5"><summary className="cursor-pointer text-sm font-medium">Per-question context recall</summary>
            <table className="w-full text-sm mt-4"><thead><tr className="text-left"><th className="py-2 label">Question</th><th className="label">Type</th>{ENGINES.map(e => <th key={e.id} className="label">{e.short}</th>)}</tr></thead>
              <tbody>{d.questions.map((q: any, i: number) => (
                <tr key={q.id} className="border-t border-line align-top"><td className="py-2.5 pr-4 text-[13px]">{q.question}</td><td className="pr-4 text-muted text-xs">{q.type}</td>
                  {ENGINES.map(e => <td key={e.id} className="font-mono text-[13px]">{res.rows[e.id][i] ? `${(res.rows[e.id][i].rcr * 100).toFixed(0)}%` : '—'}</td>)}</tr>))}</tbody></table></details>
        </> : !st?.running && <div className="card p-10 text-center text-muted text-sm">No benchmark results yet. Index documents in Chat, then run the benchmark.</div>}

        <section>
          <div className="label mb-3">Design expectations from the problem statement (reference, not measured)</div>
          <div className="card overflow-hidden"><table className="w-full text-[13px]"><thead><tr className="text-left"><th className="p-3.5 label">Dimension</th>{ENGINES.map(e => <th key={e.id} className="p-3.5 label">{e.label}</th>)}</tr></thead>
            <tbody>{SPEC.map(r => <tr key={r[0]} className="border-t border-line"><td className="px-3.5 py-3 font-medium">{r[0]}</td>{r.slice(1).map((c, i) => <td key={i} className="px-3.5 py-3 text-muted">{c}</td>)}</tr>)}
              <tr className="border-t border-line"><td className="px-3.5 py-3 font-medium">Avg latency (spec)</td><td className="px-3.5 py-3 text-muted">~450 ms</td><td className="px-3.5 py-3 text-muted">~1,200 ms</td><td className="px-3.5 py-3 text-muted">~850 ms</td></tr></tbody></table></div>
        </section>
      </div>
    </div>
  )
}
