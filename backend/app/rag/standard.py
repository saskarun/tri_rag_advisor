import time
from .. import config
from ..index import vector
from ..registry import get_registry
from .common import Timer, build_sources, synthesize


def answer(query: str, area: str, **_) -> dict:
    start, tm, reg = time.perf_counter(), Timer(), get_registry()
    k = config.HYPERPARAMS["top_k"]
    with tm.track("retrieval_ms"):
        hits = vector.search(query, k)
    srcs = build_sources(reg, [c for c, _ in hits], {c: {"score": round(s, 3)} for c, s in hits})
    text = synthesize(query, area, srcs, tm)
    return {"engine": "standard", "answer": text, "sources": srcs,
            "trace": [{"node": "vector_search", "detail": f"top-{k} dense HNSW"}, {"node": "synthesis"}],
            "timings": tm.done(start), "retrieved_ids": [s["chunk_id"] for s in srcs]}
