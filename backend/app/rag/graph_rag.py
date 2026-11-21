"""Graph RAG as a LangGraph cyclic state graph:
query_expansion -> hybrid_search -> rrf_fusion -> (loop back to hybrid_search if no graph seeds) -> rerank -> synthesis
Every node/edge can be toggled (Tab 3). Semantics: a disabled node passes state through; disabling the edge INTO a node
bypasses that node (synthesis always runs). With hybrid_search off, retrieval falls back to dense vector only."""
import re, time
from typing import TypedDict, Any
import numpy as np
from langgraph.graph import StateGraph, START, END
from .. import config
from ..index import vector
from ..index.embeddings import embed_query
from ..llm import complete
from ..registry import get_registry
from .common import Timer, build_sources, synthesize
from .fusion import rrf

NODES = [
    {"id": "query_expansion", "label": "Query Expansion", "desc": "LLM rewrites the query into alternative phrasings and domain terms."},
    {"id": "hybrid_search", "label": "Hybrid Vector/Graph Search", "desc": "Dense HNSW + BM25 + k-hop knowledge-graph traversal. Off = dense vector only."},
    {"id": "rrf_fusion", "label": "RRF Fusion", "desc": "Reciprocal Rank Fusion of dense, sparse and graph rank lists."},
    {"id": "rerank", "label": "Rerank", "desc": "Cosine re-scoring with a graph-proximity bonus."},
    {"id": "synthesis", "label": "Synthesis", "desc": "CO-STAR prompt + guardrails generate the cited answer. Always runs.", "locked": True},
]
EDGES = [
    {"id": "e_qe_hs", "source": "query_expansion", "target": "hybrid_search"},
    {"id": "e_hs_rrf", "source": "hybrid_search", "target": "rrf_fusion"},
    {"id": "e_rrf_rr", "source": "rrf_fusion", "target": "rerank"},
    {"id": "e_rr_syn", "source": "rerank", "target": "synthesis"},
    {"id": "e_loop", "source": "rrf_fusion", "target": "hybrid_search", "loop": True},
]
BLURB = "Hybrid dense + BM25 + k-hop knowledge-graph retrieval, fused and reranked, with a re-seed cycle."
_INCOMING = {"query_expansion": None, "hybrid_search": "e_qe_hs", "rrf_fusion": "e_hs_rrf", "rerank": "e_rrf_rr", "synthesis": "e_rr_syn"}


class S(TypedDict, total=False):
    query: str; area: str; expansions: list[str]; vec: list[list[str]]; bm: list[list[str]]
    graph_ranked: list[str]; graph_hops: dict; paths: list[dict]; seeds: list[str]
    fused: list[tuple]; final: list[str]; loops: int; trace: list[dict]


def answer(query: str, area: str, toggles: dict | None = None, excluded_nodes=None, excluded_edges=None, **_) -> dict:
    start, tm, reg, hp = time.perf_counter(), Timer(), get_registry(), config.HYPERPARAMS
    t = toggles or {}
    non, eon = t.get("nodes", {}), t.get("edges", {})
    on = lambda n: non.get(n, True)
    eff = lambda n: on(n) and (_INCOMING[n] is None or eon.get(_INCOMING[n], True))
    bn = set(excluded_nodes or [])
    be = {(e.split("|")[0], e.split("|")[1]) for e in (excluded_edges or []) if "|" in e}
    trace: list[dict] = []

    def log(node, t0, detail, skipped=False):
        trace.append({"node": node, "ms": round((time.perf_counter() - t0) * 1000), "detail": detail, "skipped": skipped})

    def n_expand(s: S) -> S:
        t0 = time.perf_counter()
        if not eff("query_expansion"):
            log("query_expansion", t0, "skipped", True); return {"expansions": [s["query"]]}
        with tm.track("llm_ms"):
            raw = complete("Rewrite the regulatory question into 2 alternative search queries using precise statutory/legal terminology and synonyms (e.g. authority names, Section/Rule). One per line, no numbering.",
                           s["query"], temperature=0.2, max_tokens=600)
        alts = [re.sub(r"^[-*\d.\s]+", "", l).strip() for l in raw.splitlines() if l.strip()][:2]
        log("query_expansion", t0, f"{len(alts)} rewrites")
        return {"expansions": [s["query"], *alts]}

    def n_search(s: S) -> S:
        t0 = time.perf_counter(); k = hp["top_k"] * 2
        qs = s["expansions"] if eff("hybrid_search") else s["expansions"][:1]
        with tm.track("retrieval_ms"):
            vec = [[c for c, _ in vector.search(q, k)] for q in qs]
            bm = [[c for c, _ in reg.bm25.search(q, k)] for q in qs] if eff("hybrid_search") else []
        if not eff("hybrid_search"):
            log("hybrid_search", t0, "graph/BM25 off: dense only", True)
            return {"vec": vec, "bm": [], "graph_ranked": [], "graph_hops": {}, "paths": [], "seeds": []}
        with tm.track("graph_ms"):
            seeds: list[str] = []
            for q in qs: seeds += reg.graph.match_nodes(q)
            if s.get("loops", 0) > 0 or not seeds:  # cycle: seed from entities of top dense hits
                for cid in vec[0][:3]:
                    seeds += [n for n, d in reg.graph.g.nodes(data=True) if cid in d["chunks"]]
            seeds = [x for x in dict.fromkeys(seeds) if x not in bn]
            res = reg.graph.khop(seeds, hp["hop_radius"], bn, be)
        ranked = [c for c, _ in sorted(res["chunks"].items(), key=lambda x: x[1]) if c in reg.chunks]
        log("hybrid_search", t0, f"{len(seeds)} seeds, k={hp['hop_radius']}, {len(res['nodes'])} nodes, {len(ranked)} graph chunks")
        return {"vec": vec, "bm": bm, "graph_ranked": ranked, "graph_hops": res["chunks"], "paths": res["paths"], "seeds": seeds}

    def n_fuse(s: S) -> S:
        t0 = time.perf_counter()
        if not eff("rrf_fusion"):
            log("rrf_fusion", t0, "skipped: first dense list", True)
            return {"fused": [(c, 0.0) for c in s["vec"][0]], "loops": s.get("loops", 0)}
        fused = rrf([*s["vec"], *s["bm"], s["graph_ranked"]], hp["rrf_alpha"])[: hp["top_k"] * 2]
        log("rrf_fusion", t0, f"alpha={hp['rrf_alpha']}, {len(fused)} candidates")
        return {"fused": fused}

    def loop_cond(s: S) -> str:
        again = (eon.get("e_loop", True) and eff("hybrid_search") and not s.get("graph_ranked")
                 and s.get("loops", 0) < 1 and eff("rrf_fusion"))
        return "again" if again else "next"

    def n_bump(s: S) -> S:
        trace.append({"node": "loop", "ms": 0, "detail": "no graph hits - re-seeding from top dense chunks", "skipped": False})
        return {"loops": s.get("loops", 0) + 1}

    def n_rerank(s: S) -> S:
        t0 = time.perf_counter(); k = hp["top_k"]
        if not eff("rerank"):
            log("rerank", t0, "skipped", True); return {"final": [c for c, _ in s["fused"]][:k]}
        with tm.track("retrieval_ms"):
            q = np.array(embed_query(s["query"]))
            sc = {c: float(q @ reg.vecs[c]) + 0.05 / (1 + s.get("graph_hops", {}).get(c, 9)) for c, _ in s["fused"] if c in reg.vecs}
        final = sorted(sc, key=lambda c: -sc[c])[:k]
        log("rerank", t0, f"top-{len(final)}")
        return {"final": final}

    def n_syn(s: S) -> S:
        return {}  # generation happens after the graph so the LLM call is timed separately

    g = StateGraph(S)
    for nid, fn in [("query_expansion", n_expand), ("hybrid_search", n_search), ("rrf_fusion", n_fuse), ("bump", n_bump), ("rerank", n_rerank), ("synthesis", n_syn)]:
        g.add_node(nid, fn)
    g.add_edge(START, "query_expansion"); g.add_edge("query_expansion", "hybrid_search"); g.add_edge("hybrid_search", "rrf_fusion")
    g.add_conditional_edges("rrf_fusion", loop_cond, {"again": "bump", "next": "rerank"})
    g.add_edge("bump", "hybrid_search"); g.add_edge("rerank", "synthesis"); g.add_edge("synthesis", END)
    out = g.compile().invoke({"query": query, "area": area, "loops": 0})

    final = out["final"] if eon.get("e_rr_syn", True) else [c for c, _ in out["fused"]][: hp["top_k"]]
    hops = out.get("graph_hops", {})
    srcs = build_sources(reg, final, {c: {"hop": hops.get(c)} for c in final})
    rels = [f"{p['source']} --{p['relation']}--> {p['target']} (hop {p['hop']})" for p in out.get("paths", [])[:15]]
    extra = ["[Knowledge-graph relations - use for reasoning; cite chunks [S#], not this block]\n" + "\n".join(dict.fromkeys(rels))] if rels else []
    t0 = time.perf_counter()
    text = synthesize(query, area, srcs, tm, extra)
    log("synthesis", t0, f"{len(srcs)} sources")
    return {"engine": "graph", "answer": text, "sources": srcs, "trace": trace, "graph_paths": out.get("paths", [])[:40],
            "seeds": out.get("seeds", []), "timings": tm.done(start), "retrieved_ids": final}
