async function j(r: Response) {
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail || `${r.status} ${r.statusText}`)
  return body
}
const json = (method: string, body?: unknown) => ({ method, headers: { 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })

export const api = {
  health: () => fetch('/api/health').then(j),
  docs: () => fetch('/api/documents').then(j),
  samples: () => fetch('/api/ingest/samples', { method: 'POST' }).then(j),
  upload: (files: File[], area?: string) => {
    const f = new FormData(); files.forEach(x => f.append('files', x)); if (area) f.append('practice_area', area)
    return fetch('/api/ingest', { method: 'POST', body: f }).then(j)
  },
  removeDoc: (id: string) => fetch(`/api/documents/${id}`, { method: 'DELETE' }).then(j),
  reindex: () => fetch('/api/reindex', { method: 'POST' }).then(j),
  chat: (b: unknown) => fetch('/api/chat', json('POST', b)).then(j),
  graph: () => fetch('/api/graph').then(j),
  workflow: (engine: string) => fetch(`/api/workflow?engine=${engine}`).then(j),
  config: () => fetch('/api/config').then(j),
  setConfig: (b: unknown) => fetch('/api/config', json('PUT', b)).then(j),
  kpis: () => fetch('/api/kpis').then(j),
  runBench: (toggles?: unknown) => fetch('/api/benchmark/run', json('POST', toggles ? { toggles } : undefined)).then(j),
  bench: () => fetch('/api/benchmark').then(j),
  areas: () => fetch('/api/practice-areas').then(j),
}

export const ENGINES = [
  { id: 'standard', label: 'Standard RAG', short: 'Standard' },
  { id: 'hyde', label: 'HyDE RAG', short: 'HyDE' },
  { id: 'graph', label: 'Graph RAG', short: 'Graph' },
] as const
export const AREAS = [
  { id: 'tax', label: 'Tax & Regulatory' },
  { id: 'grc', label: 'Risk Advisory & GRC' },
  { id: 'deals', label: 'Deal Advisory' },
] as const

/** Human labels for workflow nodes/edges, used in the "custom pipeline" badges. */
export const STEP_LABELS: Record<string, string> = {
  query_expansion: 'Query Expansion', dense_search: 'Dense', sparse_search: 'Sparse BM25', graph_traversal: 'Graph traversal',
  rrf_fusion: 'RRF Fusion', rerank: 'Rerank', hyde_generate: 'HyDE generation',
  e_qe_dn: 'Expansion→Dense', e_qe_sp: 'Expansion→Sparse', e_qe_gr: 'Expansion→Graph', e_dn_rrf: 'Dense→RRF', e_sp_rrf: 'Sparse→RRF',
  e_gr_rrf: 'Graph→RRF', e_rrf_rr: 'RRF→Rerank', e_rr_syn: 'Rerank→Synthesis', e_loop: 'Re-seed loop',
  e_hg_vs: 'HyDE→Search', e_vs_rrf: 'Search→RRF', e_rrf_syn: 'RRF→Synthesis',
}
type TG = { nodes: Record<string, boolean>; edges: Record<string, boolean> } | undefined
/** Ids of the nodes/edges switched off in a toggles object. */
export const disabledSteps = (t: TG): string[] =>
  [...Object.entries(t?.nodes ?? {}), ...Object.entries(t?.edges ?? {})].filter(([, v]) => v === false).map(([k]) => k)
export const stepLabel = (id: string) => STEP_LABELS[id] ?? id
