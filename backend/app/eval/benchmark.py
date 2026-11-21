import json, statistics, threading
from pathlib import Path
from .. import config
from ..rag import standard, hyde, graph_rag
from ..registry import get_registry
from . import kpis

GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text())
ENGINES = {"standard": standard.answer, "hyde": hyde.answer, "graph": graph_rag.answer}
_FILE = config.STORAGE / "benchmark.json"
STATE = {"running": False, "progress": 0, "total": 0, "error": None}


def last_result() -> dict | None:
    return json.loads(_FILE.read_text()) if _FILE.exists() else None


def disabled_steps(t: dict | None) -> list[str]:
    """Ids of nodes/edges switched off in a toggles dict."""
    t = t or {}
    return [k for grp in ("nodes", "edges") for k, v in (t.get(grp) or {}).items() if v is False]


def run_one(engine: str, q: dict, judge: bool = True, toggles: dict | None = None) -> dict:
    r = ENGINES[engine](q["question"], q["area"], toggles=toggles)
    out = {"qid": q["id"], "type": q["type"], "rcr": round(kpis.retrieval_context_recall(q["facts"], r["retrieved_ids"]), 3),
           "timings": r["timings"], "answer": r["answer"]}
    out["faithfulness"] = kpis.faithfulness(r["answer"], r["sources"])["score"] if judge else None
    return out


def _worker(judge: bool, toggles: dict):
    try:
        qs = GOLDEN["questions"]; STATE.update(running=True, progress=0, total=len(qs) * 3, error=None)
        rows = {e: [] for e in ENGINES}
        for q in qs:
            for e in ENGINES:
                rows[e].append(run_one(e, q, judge, toggles.get(e))); STATE["progress"] += 1
        er = kpis.entity_resolution_accuracy(GOLDEN["entity_links"])
        summary = {}
        for e, rs in rows.items():
            f = [r["faithfulness"] for r in rs if r["faithfulness"] is not None]
            by_type = {}
            for ty in ("keyword", "vocabulary", "multihop"):
                sub = [r["rcr"] for r in rs if r["type"] == ty]
                by_type[ty] = round(statistics.mean(sub), 3) if sub else None
            tm = {k: round(statistics.mean(r["timings"][k] for r in rs)) for k in rs[0]["timings"]}
            summary[e] = {"rcr": round(statistics.mean(r["rcr"] for r in rs), 3),
                          "faithfulness": round(statistics.mean(f), 3) if f else None,
                          "entity_resolution": er["score"] if e == "graph" else None,
                          "latency": tm, "rcr_by_type": by_type}
        res = {"summary": summary, "rows": rows, "entity_resolution": er, "hyperparams": dict(config.HYPERPARAMS),
               "embed_model": config.EMBED_MODEL,
               "pipeline": {e: disabled_steps(toggles.get(e)) for e in ENGINES}}
        _FILE.write_text(json.dumps(res))
    except Exception as e:
        STATE["error"] = str(e)
    finally:
        STATE["running"] = False


def start(judge: bool = True, toggles: dict | None = None) -> bool:
    """toggles: {engine: {"nodes": {...}, "edges": {...}}}; None/empty = default pipelines."""
    if STATE["running"]: return False
    threading.Thread(target=_worker, args=(judge, toggles or {}), daemon=True).start()
    return True
