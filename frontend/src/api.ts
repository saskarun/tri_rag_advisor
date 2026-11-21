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
  runBench: () => fetch('/api/benchmark/run', { method: 'POST' }).then(j),
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
