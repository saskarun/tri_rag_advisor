"""Graph RAG as a LangGraph cyclic state graph:

  query_expansion -> [dense_search | sparse_search | graph_traversal]  (parallel fan-out)
                  -> rrf_fusion -> (cycle: re-seed graph_traversal if it found nothing) -> rerank -> synthesis

Every node/edge can be toggled (Workflow tab). Semantics:
  * disabled node  = passes state through (a retriever contributes no ranking)
  * disabled edge INTO a node = that node is bypassed
  * disabled edge from a retriever INTO rrf_fusion = that retriever runs but its list is left out of the fusion
  * synthesis always runs; if every retriever is off/dropped, fusion falls back to a dense search."""
import re, time
from typing import TypedDict
import numpy as np
from langgraph.graph import StateGraph, START, END
from .. import config
from ..index import vector
from ..index.embeddings import embed_query
from ..llm import complete
from ..registry import get_registry
from .common import Timer, build_sources, synthesize
from .fusion import rrf

# col/row place nodes on the workflow canvas
NODES = [
    {"id": "query_expansion", "label": "Query Expansion", "col": 0, "row": 1, "desc": "LLM rewrites the query into alternative phrasings and domain terms."},
    {"id": "dense_search", "label": "Dense Vector Search", "col": 1, "row": 0, "desc": "Embeds each query variant and searches the Qdrant HNSW index (semantic similarity)."},
    {"id": "sparse_search", "label": "Sparse BM25 Search", "col": 1, "row": 1, "desc": "Keyword search - catches exact Section/Rule numbers and legal terms."},
    {"id": "graph_traversal", "label": "Graph Traversal", "col": 1, "row": 2, "desc": "Matches entities in the query, then walks k hops through the knowledge graph."},
    {"id": "rrf_fusion", "label": "RRF Fusion", "col": 2, "row": 1, "desc": "Reciprocal Rank Fusion of the dense, sparse and graph rank lists. Off = interleave without fusing."},
    {"id": "rerank", "label": "Rerank", "col": 3, "row": 1, "desc": "Cosine re-scoring with a graph-proximity bonus."},
    {"id": "synthesis", "label": "Synthesis", "col": 4, "row": 1, "desc": "CO-STAR prompt + guardrails generate the cited answer. Always runs.", "locked": True},
]
EDGES = [
    {"id": "e_qe_dn", "source": "query_expansion", "target": "dense_search"},
    {"id": "e_qe_sp", "source": "query_expansion", "target": "sparse_search"},
    {"id": "e_qe_gr", "source": "query_expansion", "target": "graph_traversal"},
    {"id": "e_dn_rrf", "source": "dense_search", "target": "rrf_fusion"},
    {"id": "e_sp_rrf", "source": "sparse_search", "target": "rrf_fusion"},
    {"id": "e_gr_rrf", "source": "graph_traversal", "target": "rrf_fusion"},
    {"id": "e_rrf_rr", "source": "rrf_fusion", "target": "rerank"},
    {"id": "e_rr_syn", "source": "rerank", "target": "synthesis"},
    {"id": "e_loop", "source": "rrf_fusion", "target": "graph_traversal", "loop": True},
]
BLURB = "Hybrid retrieval: dense + BM25 + k-hop knowledge-graph traversal run in parallel, are fused and reranked, with a re-seed cycle when the graph finds nothing."
_INCOMING = {"query_expansion": None, "dense_search": "e_qe_dn", "sparse_search": "e_qe_sp", "graph_traversal": "e_qe_gr",
             "rrf_fusion": None, "rerank": "e_rrf_rr", "synthesis": "e_rr_syn"}
_TO_RRF = {"dense_search": "e_dn_rrf", "sparse_search": "e_sp_rrf", "graph_traversal": "e_gr_rrf"}


class S(TypedDict, total=False):
    query: str; area: str; expansions: list[str]; vec: list[list[str]]; bm: list[list[str]]
    graph_ranked: list[str]; graph_hops: dict; paths: list[dict]; seeds: list[str]
    fused: list[tuple]; final: list[str]; loops: int


def answer(query: str, area: str, toggles: dict | None = None, excluded_nodes=None, excluded_edges=None, **_) -> dict:
    start, tm, reg, hp = time.perf_counter(), Timer(), get_registry(), config.HYPERPARAMS
    t = toggles or {}
    non, eon = t.get("nodes", {}), t.get("edges", {})
    on = lambda n: non.get(n, True)
    eff = lambda n: on(n) and (_INCOMING[n] is None or eon.get(_INCOMING[n], True))
    in_fusion = lambda n: eff(n) and eon.get(_TO_RRF[n], True)
    bn = set(excluded_nodes or [])
    be = {(e.split("|")[0], e.split("|")[1]) for e in (excluded_edges or []) if "|" in e}
    trace: list[dict] = []  # list.append is thread-safe; the three retrievers run in parallel

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

    def n_dense(s: S) -> S:
        t0 = time.perf_counter()
        if not eff("dense_search"):
            log("dense_search", t0, "skipped", True); return {"vec": []}
        with tm.track("retrieval_ms"):
            vec = [[c for c, _ in vector.search(q, hp["top_k"] * 2)] for q in s["expansions"]]
        log("dense_search", t0, f"{len(vec)} search(es), top-{hp['top_k'] * 2}")
        return {"vec": vec}

    def n_sparse(s: S) -> S:
        t0 = time.perf_counter()
        if not eff("sparse_search"):
            log("sparse_search", t0, "skipped", True); return {"bm": []}
        with tm.track("retrieval_ms"):
            bm = [[c for c, _ in reg.bm25.search(q, hp["top_k"] * 2)] for q in s["expansions"]]
        log("sparse_search", t0, f"{sum(len(b) for b in bm)} keyword hits")
        return {"bm": bm}

    def traverse(s: S, reseed: bool) -> S:
        t0 = time.perf_counter()
        empty = {"graph_ranked": [], "graph_hops": {}, "paths": [], "seeds": []}
        if not eff("graph_traversal"):
            log("graph_traversal", t0, "skipped", True); return empty
        with tm.track("graph_ms"):
            seeds: list[str] = []
            for q in s["expansions"]: seeds += reg.graph.match_nodes(q)
            if reseed:  # cycle: seed from the entities of the best chunks found so far
                for cid, _ in s.get("fused", [])[:3]:
                    seeds += [n for n, d in reg.graph.g.nodes(data=True) if cid in d["chunks"]]
            seeds = [x for x in dict.fromkeys(seeds) if x not in bn]
            res = reg.graph.khop(seeds, hp["hop_radius"], bn, be)
        ranked = [c for c, _ in sorted(res["chunks"].items(), key=lambda x: x[1]) if c in reg.chunks]
        log("graph_traversal", t0, f"{'re-seeded: ' if reseed else ''}{len(seeds)} seeds, k={hp['hop_radius']}, {len(res['nodes'])} nodes, {len(ranked)} chunks")
        return {"graph_ranked": ranked, "graph_hops": res["chunks"], "paths": res["paths"], "seeds": seeds}

    def n_fuse(s: S) -> S:
        t0 = time.perf_counter()
        lists: list[list[str]] = []
        if in_fusion("dense_search"): lists += s.get("vec", [])
        if in_fusion("sparse_search"): lists += s.get("bm", [])
        if in_fusion("graph_traversal"): lists.append(s.get("graph_ranked", []))
        lists = [l for l in lists if l]
        note = ""
        if not lists:  # every retriever off / dropped: keep the pipeline answerable
            with tm.track("retrieval_ms"):
                lists = [[c for c, _ in vector.search(s["query"], hp["top_k"] * 2)]]
            note = " (no retriever output: dense fallback)"
        if on("rrf_fusion"):
            fused = rrf(lists, hp["rrf_alpha"])[: hp["top_k"] * 2]
            log("rrf_fusion", t0, f"alpha={hp['rrf_alpha']}, {len(lists)} lists, {len(fused)} candidates{note}")
        else:
            seen: dict[str, float] = {}
            for i in range(max(map(len, lists))):
                for l in lists:
                    if i < len(l): seen.setdefault(l[i], 0.0)
            fused = list(seen.items())[: hp["top_k"] * 2]
            log("rrf_fusion", t0, f"skipped: interleaved {len(lists)} lists{note}", True)
        return {"fused": fused}

    def loop_cond(s: S) -> str:
        again = (eon.get("e_loop", True) and in_fusion("graph_traversal") and on("rrf_fusion")
                 and not s.get("graph_ranked") and s.get("loops", 0) < 1)
        return "again" if again else "next"

    def n_bump(s: S) -> S:
        trace.append({"node": "loop", "ms": 0, "detail": "no graph hits - re-seeding from the top fused chunks", "skipped": False})
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

    g = StateGraph(S)
    g.add_node("query_expansion", n_expand); g.add_node("dense_search", n_dense); g.add_node("sparse_search", n_sparse)
    g.add_node("graph_traversal", lambda s: traverse(s, False)); g.add_node("graph_loop", lambda s: traverse(s, True))
    g.add_node("rrf_fusion", n_fuse); g.add_node("bump", n_bump); g.add_node("rerank", n_rerank)
    g.add_node("synthesis", lambda s: {})  # generation runs after the graph so the LLM call is timed separately
    g.add_edge(START, "query_expansion")
    for n in ("dense_search", "sparse_search", "graph_traversal"): g.add_edge("query_expansion", n)
    g.add_edge(["dense_search", "sparse_search", "graph_traversal"], "rrf_fusion")  # join: wait for all three
    g.add_conditional_edges("rrf_fusion", loop_cond, {"again": "bump", "next": "rerank"})
    g.add_edge("bump", "graph_loop"); g.add_edge("graph_loop", "rrf_fusion")
    g.add_edge("rerank", "synthesis"); g.add_edge("synthesis", END)
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
