# TriRAG Advisor

PwC India · Multi-RAG benchmark

Compare **Standard RAG**, **HyDE RAG** and **Graph RAG** (LangChain + LangGraph) on Indian regulatory documents
(CBDT/CBIC tax, RBI KYC/PMLA, SPAs), under three practice-area guardrails, with a 5-tab UI.

## Run

```bash
cp .env.example .env            # set OPENROUTER_API_KEY (model: anthropic/claude-sonnet-5.5)
cd backend && pip install -r requirements.txt
python data/make_samples.py     # (already generated) fictional sample PDF/DOCX/JSON in backend/data/samples
python -m uvicorn app.main:app --port 8765

cd ../frontend && npm install
npm run dev                     # http://localhost:5173 (proxies /api to :8765)
# or: npm run build   -> backend serves frontend/dist at http://localhost:8765 after a restart
```

First run downloads `BAAI/bge-large-en-v1.5` (~1.3 GB). For a quick dev loop set
`EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2` (384-d) in `.env`.
Tests: `cd backend && python -m pytest tests`.

## The 6 steps (Graph RAG pipeline)

| Step | Where |
|---|---|
| 1 Data format | `app/ingestion/loaders.py` — PDF (`UnstructuredPDFLoader`, pypdf fallback), DOCX, JSON tables; provenance metadata on every document |
| 2 Chunking | `app/ingestion/chunker.py` — token-based `RecursiveCharacterTextSplitter`, clause-aware separators; `app/graph/extractor.py` LLM entity-relation extraction |
| 3 Tokenization | `app/ingestion/tokenizer.py` (HF tokenizer of the embedding model), `app/graph/normalizer.py` (alias → canonical entity) |
| 4 Embedding | `app/index/embeddings.py` (bge-large, 1024-d), `app/graph/node2vec.py` (structural embeddings) |
| 5 Indexing | Qdrant HNSW (`app/index/vector.py`) + BM25 + graph adjacency (`app/graph/store.py`) |
| 6 Vector store | Qdrant embedded/on-disk, NetworkX graph (`backend/storage/`); optional Neo4j mirror via `GRAPH_BACKEND=neo4j` |

## Things to know

- **Embedded DBs.** Docker is not required: Qdrant runs in local mode and the graph is NetworkX. With
  `GRAPH_BACKEND=neo4j` (+ `NEO4J_*` vars) the graph is *mirrored* to Neo4j on every index build; k-hop traversal still
  runs on the in-memory NetworkX copy.
- **Chunk size vs. embedding limit.** The spec asks for 600-token chunks, but bge-large accepts 512 tokens. The chunker
  caps at 510. Overlap/size are editable in the Telemetry tab (re-index required).
- **Node2Vec** is implemented with numpy (random walks + PPMI + SVD) because `gensim` has no Python 3.14 wheel.
- **Faithfulness** is LLM-judged and approximate. **Retrieval context recall** matches ground-truth fact strings
  (`backend/app/eval/golden.json`) against retrieved chunks. Sample documents are fictional.
- Small corpora saturate recall: with 600-token chunks each sample document is a single chunk, so every engine scores
  100%. Use a smaller chunk size (e.g. 120) or upload more documents for a discriminating benchmark.
