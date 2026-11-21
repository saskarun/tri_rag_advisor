import time
from .. import config
from ..index import vector
from ..registry import get_registry
from .common import Timer, build_sources, synthesize

NODES = [
    {"id": "vector_search", "label": "Dense Vector Search", "desc": "Embed the query and fetch the top-k nearest chunks from the Qdrant HNSW index.", "locked": True},
    {"id": "synthesis", "label": "Synthesis", "desc": "CO-STAR prompt + guardrails generate the cited answer.", "locked": True},
]
EDGES = [{"id": "e_vs_syn", "source": "vector_search", "target": "synthesis"}]
BLURB = "Baseline: one dense lookup, then synthesis. No optional stages, so there is nothing to toggle."


def answer(query: str, area: str, **_) -> dict:
    start, tm, reg = time.perf_counter(), Timer(), get_registry()
    k = config.HYPERPARAMS["top_k"]
    t0 = time.perf_counter()
    with tm.track("retrieval_ms"):
        hits = vector.search(query, k)
    trace = [{"node": "vector_search", "ms": round((time.perf_counter() - t0) * 1000), "detail": f"top-{k} dense HNSW", "skipped": False}]
    srcs = build_sources(reg, [c for c, _ in hits], {c: {"score": round(s, 3)} for c, s in hits})
    t0 = time.perf_counter()
    text = synthesize(query, area, srcs, tm)
    trace.append({"node": "synthesis", "ms": round((time.perf_counter() - t0) * 1000), "detail": f"{len(srcs)} sources", "skipped": False})
    return {"engine": "standard", "answer": text, "sources": srcs, "trace": trace,
            "timings": tm.done(start), "retrieved_ids": [s["chunk_id"] for s in srcs]}
