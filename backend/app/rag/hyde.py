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


def _hypotheses(query: str, area: str, n: int) -> list[str]:
    angles = (ANGLES.get(area, ANGLES["tax"]) * 3)[:n]
    sys = "You write short, plausible passages in the style of Indian regulatory/legal documents, used only for retrieval. Output ONLY the passage (60-90 words)."
    from concurrent.futures import ThreadPoolExecutor
    def one(a): return complete(sys, f"Question: {query}\nWrite a hypothetical passage answering it from the angle of: {a}.", temperature=0.7, max_tokens=700)
    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(one, angles))


def answer(query: str, area: str, **_) -> dict:
    start, tm, reg = time.perf_counter(), Timer(), get_registry()
    hp = config.HYPERPARAMS
    with tm.track("llm_ms"):
        hyps = _hypotheses(query, area, hp["hyde_n"])
    with tm.track("retrieval_ms"):
        vecs = embed_docs(hyps)  # passages embedded as documents (no query instruction)
        lists = [[c for c, _ in vector.search_vec(v, hp["top_k"])] for v in vecs]
        lists.append([c for c, _ in vector.search(query, hp["top_k"])])
        fused = rrf(lists, hp["rrf_alpha"])[: hp["top_k"]]
    srcs = build_sources(reg, [c for c, _ in fused], {c: {"score": round(s, 4)} for c, s in fused})
    text = synthesize(query, area, srcs, tm)
    return {"engine": "hyde", "answer": text, "sources": srcs, "hypotheses": hyps,
            "trace": [{"node": "hyde_generate", "detail": f"{len(hyps)} hypotheses"}, {"node": "vector_search", "detail": "per-hypothesis"},
                      {"node": "rrf_fusion"}, {"node": "synthesis"}],
            "timings": tm.done(start), "retrieved_ids": [s["chunk_id"] for s in srcs]}
