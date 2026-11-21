# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project name: **TriRAG Advisor**. Spec: `PwC India Multi-RAG Problem Statement.pdf` (the authoritative requirements). Overview and setup: `README.md`.

## Commands

```bash
# backend (Python 3.14, venv at ~/venv)
cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --port 8765        # NOT 8000: another app ("HyDE RAG") often occupies it on this machine
python -m pytest tests                            # all tests
python -m pytest tests/test_core.py -k khop       # single test
python data/make_samples.py                       # regenerate the fictional sample PDFs/DOCX/JSON

# frontend
cd frontend && npm install && npm run dev         # :5173, proxies /api -> :8765 (see vite.config.ts)
npx tsc --noEmit                                  # type-check;  npm run build  -> frontend/dist (served by FastAPI if present at startup)
```

Config comes from the repo-root `.env` (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `EMBED_MODEL`, `GRAPH_BACKEND`); never print or commit it. LLM = Claude via OpenRouter through `langchain-openai` (`app/llm.py`). The model spends part of `max_tokens` on reasoning, so keep budgets generous (small ones silently return empty/truncated text).

## Architecture

- `app/registry.py` is the single corpus owner. `Registry.reindex()` does a **full rebuild** (load → chunk → embed → Qdrant → BM25 → LLM entity extraction → graph + Node2Vec) from `storage/sources.json`; any ingest/delete/chunk-param change goes through it. State lives in `backend/storage/` (Qdrant local, `graph.json`, extraction cache, `benchmark.json`, uploads).
- Hyperparameters are a mutable dict in `app/config.py` (`HYPERPARAMS`), edited at runtime via `PUT /api/config`; engines read them per request. Chunk params only take effect after reindex.
- Three engines share one signature `answer(query, area, **opts) -> {answer, sources, trace, timings, retrieved_ids}` and the same `app/rag/common.py` synthesis + CO-STAR prompt (`app/prompts.py`, practice-area guardrails). Latency is split into `retrieval_ms / graph_ms / llm_ms` via `Timer`.
  - `standard.py`: dense top-k. `hyde.py`: N LLM hypotheses → per-hypothesis search → RRF.
  - `graph_rag.py`: a **LangGraph `StateGraph` rebuilt per request** (query_expansion → hybrid_search → rrf_fusion → [cycle back if no graph hits] → rerank → synthesis). UI toggles arrive as `toggles.nodes/edges`; semantics: disabled node = pass-through, disabled edge = bypass the node it feeds, synthesis is locked on, hybrid_search off = dense only. `NODES/EDGES` in this file also feed `/api/workflow`, so the canvas and the engine cannot drift apart.
  - Graph filters from the 3D canvas arrive as `excluded_nodes/excluded_edges` (edge id = `"src|tgt|key"`) and apply only to Graph RAG traversal (`GraphStore.khop(blocked_*)`).
- `app/graph/`: `extractor.py` (LLM JSON extraction, deterministic rule-based fallback, disk cache), `normalizer.py` (alias table + company-suffix merging → canonical nodes), `store.py` (NetworkX MultiDiGraph, k-hop BFS, Neo4j mirror), `node2vec.py` (numpy; gensim has no py3.14 wheel).
- `app/eval/`: `kpis.py` (RCR via fact-string match, LLM-judge faithfulness, entity-resolution accuracy), `benchmark.py` (runs `golden.json` × 3 engines in a background thread; progress in `STATE`), results cached to `storage/benchmark.json`.
- Frontend (`frontend/src`): one tab component per spec tab in `tabs/`; `App.tsx` owns state shared across tabs (workflow toggles, graph exclusions) and keeps Chat mounted so the conversation survives tab switches. Theme is CSS variables + a `dark` class (default dark). The chat composer animates from centre to bottom with a CSS `top/transform` transition (`.composer-wrap`). `components/Markdown.tsx` turns `[S#]` into clickable citation chips.

## Gotchas

- Spec says 600-token chunks but bge-large has a 512-token limit; the chunker caps at 510.
- Each sample doc is < 600 tokens, so with default chunking every doc is one chunk and all engines hit 100% recall; benchmark with a smaller chunk size or a larger corpus.
- Don't run `pkill -f "uvicorn ..."` from the shell tool (it matches and kills its own shell); kill by PID from `ss -ltnp`.
