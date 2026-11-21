"""Multi-hypothesis HyDE: N synthetic passages from distinct regulatory angles."""
import time
from .. import config
from ..index import vector
from ..index.embeddings import embed_docs
from ..llm import complete
from ..registry import get_registry
from .common import Timer, build_sources, synthesize
from .fusion import rrf

ANGLES = {
    "tax": ["statutory text (Section/Rule wording)", "retrospective vs prospective applicability and amendments", "compliance procedure, rates and penalties"],
    "grc": ["regulatory obligation text (Master Direction / Act)", "internal control mapping and procedures", "penalties and enforcement consequences"],
    "deals": ["contract clause wording (indemnity, MAC, conditions)", "financial exposure, caps and thresholds", "regulatory approvals and foreign-investment compliance"],
}
NODES = [
    {"id": "hyde_generate", "label": "Multi-HyDE Generation", "desc": "LLM writes N synthetic passages, each from a distinct regulatory angle. Off = search with the raw query only."},
    {"id": "vector_search", "label": "Dense Vector Search", "desc": "Each passage (and the original query) is embedded and searched in the HNSW index.", "locked": True},
    {"id": "rrf_fusion", "label": "RRF Fusion", "desc": "Reciprocal Rank Fusion merges the per-hypothesis rank lists. Off = concatenate in order."},
    {"id": "synthesis", "label": "Synthesis", "desc": "CO-STAR prompt + guardrails generate the cited answer.", "locked": True},
]
EDGES = [
    {"id": "e_hg_vs", "source": "hyde_generate", "target": "vector_search"},
    {"id": "e_vs_rrf", "source": "vector_search", "target": "rrf_fusion"},
    {"id": "e_rrf_syn", "source": "rrf_fusion", "target": "synthesis"},
]
BLURB = "Generates hypothetical answers first, then retrieves with them to bridge vocabulary gaps."
_INCOMING = {"hyde_generate": None, "vector_search": "e_hg_vs", "rrf_fusion": "e_vs_rrf", "synthesis": "e_rrf_syn"}


def _hypotheses(query: str, area: str, n: int) -> list[str]:
    angles = (ANGLES.get(area, ANGLES["tax"]) * 3)[:n]
    sys = "You write short, plausible passages in the style of Indian regulatory/legal documents, used only for retrieval. Output ONLY the passage (60-90 words)."
    from concurrent.futures import ThreadPoolExecutor
    def one(a): return complete(sys, f"Question: {query}\nWrite a hypothetical passage answering it from the angle of: {a}.", temperature=0.7, max_tokens=700)
    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(one, angles))


def answer(query: str, area: str, toggles: dict | None = None, **_) -> dict:
    start, tm, reg, hp = time.perf_counter(), Timer(), get_registry(), config.HYPERPARAMS
    t = toggles or {}
    non, eon = t.get("nodes", {}), t.get("edges", {})
    eff = lambda n: non.get(n, True) and (_INCOMING[n] is None or eon.get(_INCOMING[n], True))
    trace = []
    log = lambda node, t0, detail, skipped=False: trace.append({"node": node, "ms": round((time.perf_counter() - t0) * 1000), "detail": detail, "skipped": skipped})

    t0 = time.perf_counter(); hyps: list[str] = []
    if eff("hyde_generate"):
        with tm.track("llm_ms"):
            hyps = _hypotheses(query, area, hp["hyde_n"])
        log("hyde_generate", t0, f"{len(hyps)} hypotheses")
    else:
        log("hyde_generate", t0, "skipped: raw query only", True)

    t0 = time.perf_counter()
    with tm.track("retrieval_ms"):
        lists = [[c for c, _ in vector.search_vec(v, hp["top_k"])] for v in (embed_docs(hyps) if hyps else [])]  # passages embedded as documents
        lists.append([c for c, _ in vector.search(query, hp["top_k"])])
    log("vector_search", t0, f"{len(lists)} search(es)")

    t0 = time.perf_counter()
    if eff("rrf_fusion"):
        fused = rrf(lists, hp["rrf_alpha"])[: hp["top_k"]]
        log("rrf_fusion", t0, f"alpha={hp['rrf_alpha']}")
    else:
        seen: dict[str, float] = {}
        for lst in lists:
            for c in lst: seen.setdefault(c, 0.0)
        fused = list(seen.items())[: hp["top_k"]]
        log("rrf_fusion", t0, "skipped: concatenated", True)

    srcs = build_sources(reg, [c for c, _ in fused], {c: {"score": round(s, 4)} for c, s in fused})
    t0 = time.perf_counter()
    text = synthesize(query, area, srcs, tm)
    log("synthesis", t0, f"{len(srcs)} sources")
    return {"engine": "hyde", "answer": text, "sources": srcs, "hypotheses": hyps, "trace": trace,
            "timings": tm.done(start), "retrieved_ids": [s["chunk_id"] for s in srcs]}
