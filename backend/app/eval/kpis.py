"""The 4 core KPIs."""
import json, re
from ..registry import get_registry
from ..llm import complete


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9. ]", " ", s.lower()).replace("  ", " ")


def retrieval_context_recall(facts: list[str], chunk_ids: list[str]) -> float:
    """% of ground-truth facts present in the retrieved chunks."""
    reg = get_registry()
    text = _norm(" ".join(reg.chunks[c].page_content for c in chunk_ids if c in reg.chunks))
    return sum(_norm(f) in text for f in facts) / len(facts) if facts else 0.0


def faithfulness(answer: str, sources: list[dict]) -> dict:
    """LLM-judge: supported claims / total claims (0-1). Approximate by nature."""
    ctx = "\n\n".join(f"[S{s['n']}] {s['text']}" for s in sources)
    sys = ('You audit an answer against its sources. Split the answer into atomic factual claims (ignore headings, '
           'the Gaps section and generic disclaimers). For each claim decide if the sources directly support it. '
           'Return ONLY JSON: {"claims":[{"claim":str,"supported":bool}]}')
    try:
        raw = complete(sys, f"SOURCES:\n{ctx}\n\nANSWER:\n{answer}", temperature=0.0, max_tokens=3000)
        claims = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))["claims"]
        n = len(claims)
        return {"score": round(sum(bool(c["supported"]) for c in claims) / n, 3) if n else 1.0, "claims": n}
    except Exception as e:
        return {"score": None, "claims": 0, "error": str(e)[:120]}


def entity_resolution_accuracy(links: list[dict]) -> dict:
    """Gold mention->canonical links vs the built graph (mentions absent from the corpus are skipped)."""
    g = get_registry().graph.g
    ok = tot = 0
    for l in links:
        m = l["mention"].lower().rstrip(".")
        node = next((n for n, d in g.nodes(data=True) if m in {a.lower().rstrip(".") for a in d["aliases"]} or m == n.lower().rstrip(".")), None)
        if node is None: continue
        tot += 1
        good = node == l["canonical"] and len(g.nodes[node]["docs"]) >= l.get("min_docs", 1)
        ok += good
    return {"score": round(ok / tot, 3) if tot else None, "checked": tot, "correct": ok}
