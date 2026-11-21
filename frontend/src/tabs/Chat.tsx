import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Paperclip, FileText, X, Sparkles, Timer, ShieldCheck, ChevronDown, UploadCloud, Loader2 } from 'lucide-react'
import { api, AREAS, ENGINES } from '../api'
import Markdown from '../components/Markdown'
import type { Shared } from '../App'

const SUGGEST: Record<string, string[]> = {
  tax: ['What is the e-invoicing turnover threshold and is it prospective or retrospective?', 'How is ISD credit distributed and what happens on wrong distribution?'],
  grc: ['How often is re-KYC required by risk category, and which control maps to it?', 'What are the STR filing timelines and penalties for KYC non-compliance?'],
  deals: ['What does the Seller indemnity cover, and what is the cap and basket?', 'When can the Buyer terminate under the MAC clause?'],
}

export default function Chat({ shared, messages, setMessages }: { shared: Shared; messages: any[]; setMessages: (f: any) => void }) {
  const [engine, setEngine] = useState('graph')
  const [area, setArea] = useState('tax')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [docs, setDocs] = useState<any[]>([])
  const [busy, setBusy] = useState('')
  const [drag, setDrag] = useState(false)
  const [notice, setNotice] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const empty = messages.length === 0

  const refresh = () => api.docs().then(d => setDocs(d.documents)).catch(() => {})
  useEffect(() => { refresh() }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, loading])
  useEffect(() => { const t = taRef.current; if (t) { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 180) + 'px' } }, [input])

  const flash = (m: string) => { setNotice(m); setTimeout(() => setNotice(''), 4500) }
  const upload = async (files: File[]) => {
    if (!files.length) return
    setBusy(`Indexing ${files.length} file(s) — chunking, embedding, building graph…`)
    try { await api.upload(files, area); await refresh() } catch (e: any) { flash(e.message) } finally { setBusy('') }
  }
  const loadSamples = async () => {
    setBusy('Indexing sample documents — chunking, embedding, building graph…')
    try { await api.samples(); await refresh() } catch (e: any) { flash(e.message) } finally { setBusy('') }
  }
  const remove = async (id: string) => { setBusy('Re-indexing…'); try { await api.removeDoc(id); await refresh() } finally { setBusy('') } }

  const send = async (text = input) => {
    const q = text.trim(); if (!q || loading) return
    setInput(''); setLoading(true)
    setMessages((m: any[]) => [...m, { role: 'user', text: q }])
    try {
      const res = await api.chat({
        message: q, engine, practice_area: area, toggles: shared.toggles[engine],
        excluded_nodes: shared.excludedNodes, excluded_edges: shared.excludedEdges,
      })
      setMessages((m: any[]) => [...m, { role: 'assistant', text: res.answer, res, engine, area }])
    } catch (e: any) {
      setMessages((m: any[]) => [...m, { role: 'assistant', error: true, text: e.message }])
    } finally { setLoading(false) }
  }

  return (
    <div className="relative h-full overflow-hidden"
      onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={e => { if (e.currentTarget === e.target) setDrag(false) }}
      onDrop={e => { e.preventDefault(); setDrag(false); upload([...e.dataTransfer.files]) }}>

      {/* conversation */}
      <div className="absolute inset-0 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-5 pt-8 pb-56 space-y-8">
          {messages.map((m, i) => <Message key={i} m={m} />)}
          {loading && (
            <div className="flex items-center gap-3 text-muted text-sm rise">
              <span className="flex gap-1"><i className="dot" /><i className="dot" /><i className="dot" /></span>
              {ENGINES.find(e => e.id === engine)?.label} is retrieving and reasoning…
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {/* composer: centred when empty, animates to the bottom and pins after the first message */}
      <div className="composer-wrap absolute inset-x-0 px-5 z-10 pointer-events-none"
        style={{ top: empty ? '46%' : '100%', transform: empty ? 'translateY(-50%)' : 'translateY(-100%)' }}>
        <div className={`max-w-3xl mx-auto pointer-events-auto ${empty ? '' : 'pb-3 pt-10 bg-gradient-to-t from-bg from-75% to-transparent'}`}>
          <div className={`text-center mb-8 transition-all duration-500 overflow-hidden ${empty ? 'opacity-100 max-h-40' : 'opacity-0 max-h-0 !mb-0'}`}>
            <div className="inline-flex items-center gap-2 text-muted text-xs mb-3 border border-line rounded-full px-3 py-1"><Sparkles size={12} />Domain-grounded compliance QA</div>
            <h1 className="text-[34px] font-semibold tracking-tight">What would you like to verify?</h1>
            <p className="text-muted text-sm mt-2">Choose a practice area and RAG engine, then ask. Answers are cited and guard-railed.</p>
          </div>

          <div className="card shadow-[0_8px_40px_-12px_rgba(0,0,0,.35)] p-3">
            <textarea ref={taRef} rows={1} value={input} placeholder="Ask about circulars, KYC obligations, SPA clauses…"
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              className="w-full resize-none bg-transparent outline-none px-2 pt-1.5 pb-2 text-[15px] placeholder:text-muted" />
            <div className="flex items-center gap-2 flex-wrap">
              <button className="btn !p-2 !rounded-full" title="Upload PDF / DOCX / JSON" onClick={() => fileRef.current?.click()}><Paperclip size={15} /></button>
              <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.json" onChange={e => { upload([...(e.target.files ?? [])]); e.target.value = '' }} />
              <select className="pill-select" value={area} onChange={e => setArea(e.target.value)} title="Practice area (guardrails)">
                {AREAS.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
              </select>
              <select className="pill-select" value={engine} onChange={e => setEngine(e.target.value)} title="RAG engine">
                {ENGINES.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
              </select>
              {engine === 'graph' && (shared.excludedNodes.length > 0 || shared.excludedEdges.length > 0) &&
                <button className="text-[11.5px] text-warn border border-line rounded-full px-2.5 py-1" onClick={() => shared.goto('graph')}>
                  {shared.excludedNodes.length + shared.excludedEdges.length} graph filter(s)</button>}
              <button onClick={() => send()} disabled={!input.trim() || loading} className="btn btn-primary !p-2 ml-auto !rounded-full"><ArrowUp size={16} /></button>
            </div>
          </div>

          {/* documents */}
          <div className="mt-3 flex flex-wrap items-center gap-2 justify-center text-xs min-h-8">
            {busy ? <span className="flex items-center gap-2 text-muted"><Loader2 size={13} className="animate-spin" />{busy}</span> : <>
              {docs.length === 0 && <button className="btn !text-xs" onClick={loadSamples}><FileText size={13} />Load sample documents (4)</button>}
              {docs.length === 0 && <span className="text-muted">or drag & drop PDF / DOCX / JSON anywhere</span>}
              {!empty && docs.length > 0 && <span className="text-muted text-[11.5px]">{docs.length} documents indexed · attach more with the paperclip</span>}
              {empty && docs.map(d => (
                <span key={d.doc_id} className="group inline-flex items-center gap-1.5 border border-line rounded-full pl-2.5 pr-1.5 py-1 bg-panel text-muted">
                  <FileText size={12} /><span className="max-w-44 truncate text-fg/80" title={d.filename}>{d.filename}</span>
                  <button onClick={() => remove(d.doc_id)} className="opacity-50 hover:opacity-100"><X size={12} /></button>
                </span>))}
              {docs.length > 0 && empty && SUGGEST[area].map(s => <button key={s} className="btn !text-xs !font-normal" onClick={() => send(s)}>{s}</button>)}
            </>}
            {notice && <span className="text-bad">{notice}</span>}
          </div>
        </div>
      </div>

      {drag && <div className="absolute inset-0 z-20 grid place-items-center bg-bg/80 backdrop-blur-sm border-2 border-dashed border-line m-4 rounded-3xl">
        <div className="text-center"><UploadCloud className="mx-auto mb-3 text-muted" size={34} /><div className="font-medium">Drop PDF, DOCX or JSON to index</div></div></div>}
    </div>
  )
}

function Message({ m }: { m: any }) {
  const [open, setOpen] = useState<number | null>(null)
  const [showSrc, setShowSrc] = useState(false)
  if (m.role === 'user') return <div className="flex justify-end rise"><div className="bg-panel2 border border-line rounded-2xl rounded-br-md px-4 py-2.5 max-w-[85%] text-[14.5px] whitespace-pre-wrap">{m.text}</div></div>
  if (m.error) return <div className="rise text-sm text-bad border border-bad/30 bg-bad/5 rounded-xl px-4 py-3">{m.text}</div>
  const r = m.res, t = r.timings, f = r.faithfulness?.score
  return (
    <div className="rise">
      <Markdown text={m.text} onCite={n => { setShowSrc(true); setOpen(n) }} />
      <div className="mt-4 flex flex-wrap items-center gap-2 text-[11.5px] text-muted">
        <span className="border border-line rounded-full px-2.5 py-1 text-fg/80">{ENGINES.find(e => e.id === m.engine)?.label}</span>
        <span className="border border-line rounded-full px-2.5 py-1 flex items-center gap-1.5" title={`retrieval ${t.retrieval_ms} ms · graph ${t.graph_ms} ms · LLM ${t.llm_ms} ms`}>
          <Timer size={11} />{(t.total_ms / 1000).toFixed(1)}s <span className="opacity-60">· ret {t.retrieval_ms} · gr {t.graph_ms} · llm {t.llm_ms} ms</span></span>
        {f != null && <span className="border border-line rounded-full px-2.5 py-1 flex items-center gap-1.5" title={`${r.faithfulness.claims} claims judged by LLM`}>
          <ShieldCheck size={11} className={f >= 0.9 ? 'text-good' : f >= 0.7 ? 'text-warn' : 'text-bad'} />Faithfulness {f.toFixed(2)}</span>}
        <button className="border border-line rounded-full px-2.5 py-1 flex items-center gap-1 hover:bg-panel2" onClick={() => setShowSrc(!showSrc)}>
          Sources ({r.sources.length})<ChevronDown size={11} className={showSrc ? 'rotate-180' : ''} /></button>
      </div>
      {showSrc && (
        <div className="mt-3 grid gap-2">
          {r.sources.map((s: any) => (
            <div key={s.n} onClick={() => setOpen(open === s.n ? null : s.n)}
              className={`card !rounded-xl px-3.5 py-2.5 cursor-pointer text-[12.5px] transition-colors ${open === s.n ? '!border-fg/40' : ''}`}>
              <div className="flex items-center gap-2"><span className="cite !m-0">S{s.n}</span><span className="font-medium truncate">{s.filename}</span>
                <span className="text-muted">p.{s.page}{s.clause ? ` · ${s.clause}` : ''}{s.hop != null ? ` · hop ${s.hop}` : ''}</span></div>
              <p className={`mt-1.5 text-muted leading-relaxed ${open === s.n ? '' : 'line-clamp-2'}`}>{s.text}</p>
            </div>))}
        </div>)}
    </div>
  )
}
