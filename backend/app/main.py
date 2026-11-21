import collections, shutil, time
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import config
from .prompts import PRACTICE_AREAS, system_prompt
from .registry import get_registry, UPLOADS
from .rag import standard, hyde, graph_rag
from .eval import kpis, benchmark

app = FastAPI(title="TriRAG Advisor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
RECENT = collections.deque(maxlen=50)  # live KPI telemetry from chat
ENGINES = {"standard": standard.answer, "hyde": hyde.answer, "graph": graph_rag.answer}


@app.on_event("startup")
def _warm():
    # load/rebuild the corpus in the background so the first page load doesn't wait on it
    import threading
    threading.Thread(target=get_registry, daemon=True).start()


class ChatReq(BaseModel):
    message: str
    engine: str = "graph"
    practice_area: str = "tax"
    toggles: dict | None = None
    excluded_nodes: list[str] = []
    excluded_edges: list[str] = []
    evaluate: bool = True


@app.get("/api/health")
def health():
    return {"ok": True, "llm_configured": bool(config.OPENROUTER_API_KEY), "model": config.OPENROUTER_MODEL,
            "embed_model": config.EMBED_MODEL, "graph_backend": config.GRAPH_BACKEND}


@app.get("/api/practice-areas")
def areas():
    return [{"id": k, **v} for k, v in PRACTICE_AREAS.items()]


@app.get("/api/documents")
def documents():
    reg = get_registry()
    return {"documents": reg.documents(), "index": reg.last_index}


@app.post("/api/ingest")
async def ingest(files: list[UploadFile] = File(...), practice_area: str | None = Form(None)):
    reg = get_registry()
    for f in files:
        if Path(f.filename).suffix.lower() not in (".pdf", ".docx", ".json"):
            raise HTTPException(400, f"Unsupported file type: {f.filename} (PDF, DOCX, JSON only)")
        dest = UPLOADS / Path(f.filename).name
        with dest.open("wb") as o: shutil.copyfileobj(f.file, o)
        reg.add_file(dest, practice_area)
    return reg.reindex()


@app.post("/api/ingest/samples")
def ingest_samples():
    return get_registry().add_samples()


@app.delete("/api/documents/{doc_id}")
def delete_doc(doc_id: str):
    return get_registry().remove(doc_id)


@app.post("/api/reindex")
def reindex():
    return get_registry().reindex()


@app.post("/api/chat")
def chat(req: ChatReq):
    if req.engine not in ENGINES: raise HTTPException(400, "engine must be standard|hyde|graph")
    if req.practice_area not in PRACTICE_AREAS: raise HTTPException(400, "unknown practice area")
    reg = get_registry()
    if not reg.chunks: raise HTTPException(409, "No documents indexed. Upload documents or load the samples first.")
    try:
        r = ENGINES[req.engine](req.message, req.practice_area, toggles=req.toggles,
                                excluded_nodes=req.excluded_nodes, excluded_edges=req.excluded_edges)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"{type(e).__name__}: {str(e)[:300]}")
    r["practice_area"] = req.practice_area
    if req.evaluate:
        r["faithfulness"] = kpis.faithfulness(r["answer"], r["sources"])
    RECENT.append({"ts": time.time(), "engine": req.engine, "timings": r["timings"],
                   "faithfulness": (r.get("faithfulness") or {}).get("score")})
    return r


@app.get("/api/graph")
def graph():
    return get_registry().graph.to_json()


@app.get("/api/config")
def get_config():
    return config.HYPERPARAMS


@app.put("/api/config")
def put_config(body: dict):
    changed_chunks = False
    for k, v in body.items():
        if k not in config.HYPERPARAMS: raise HTTPException(400, f"unknown hyperparameter {k}")
        v = int(v)
        if v < 0: raise HTTPException(400, f"{k} must be >= 0")
        if k in ("chunk_size", "chunk_overlap") and v != config.HYPERPARAMS[k]: changed_chunks = True
        config.HYPERPARAMS[k] = v
    if config.HYPERPARAMS["chunk_overlap"] >= config.HYPERPARAMS["chunk_size"]:
        raise HTTPException(400, "chunk_overlap must be smaller than chunk_size")
    return {"hyperparams": config.HYPERPARAMS, "needs_reindex": changed_chunks}


WORKFLOWS = {"standard": standard, "hyde": hyde, "graph": graph_rag}


@app.get("/api/workflow")
def workflow(engine: str = "graph"):
    m = WORKFLOWS.get(engine)
    if not m: raise HTTPException(400, "engine must be standard|hyde|graph")
    return {"engine": engine, "nodes": m.NODES, "edges": m.EDGES, "blurb": m.BLURB}


@app.get("/api/kpis")
def get_kpis():
    reg = get_registry()
    er = kpis.entity_resolution_accuracy(benchmark.GOLDEN["entity_links"]) if reg.chunks else {"score": None}
    return {"recent": list(RECENT), "entity_resolution": er, "benchmark": (benchmark.last_result() or {}).get("summary"),
            "index": reg.last_index, "hyperparams": config.HYPERPARAMS}


@app.post("/api/benchmark/run")
def bench_run(judge: bool = True, toggles: dict | None = Body(default=None, embed=True)):
    """Optional body {"toggles": {engine: {nodes, edges}}} benchmarks the user's custom pipelines instead of the defaults."""
    if not get_registry().chunks: raise HTTPException(409, "No documents indexed.")
    return {"started": benchmark.start(judge, toggles), **benchmark.STATE}


@app.get("/api/benchmark")
def bench_get():
    return {"state": benchmark.STATE, "result": benchmark.last_result(), "questions": benchmark.GOLDEN["questions"]}


_dist = config.ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
