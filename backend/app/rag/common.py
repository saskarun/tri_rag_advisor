"""Shared engine plumbing: source blocks, synthesis, timers."""
import time
from contextlib import contextmanager
from ..prompts import system_prompt, user_prompt
from ..llm import complete


class Timer:
    def __init__(self): self.t = {"retrieval_ms": 0.0, "graph_ms": 0.0, "llm_ms": 0.0}

    @contextmanager
    def track(self, key):
        s = time.perf_counter()
        try: yield
        finally: self.t[key] += (time.perf_counter() - s) * 1000

    def done(self, start):
        self.t["total_ms"] = (time.perf_counter() - start) * 1000
        return {k: round(v) for k, v in self.t.items()}


def build_sources(reg, chunk_ids: list[str], extra: dict[str, dict] | None = None) -> list[dict]:
    out = []
    for i, cid in enumerate(chunk_ids, start=1):
        c = reg.chunks[cid]; m = c.metadata
        out.append({"n": i, "chunk_id": cid, "filename": m["filename"], "page": m.get("page"), "clause": m.get("clause"),
                    "practice_area": m["practice_area"], "text": c.page_content, **(extra or {}).get(cid, {})})
    return out


def synthesize(question: str, area: str, sources: list[dict], timer: Timer, extra_blocks: list[str] | None = None) -> str:
    blocks = [f"[S{s['n']}] ({s['filename']}, page {s['page']}{', ' + s['clause'] if s['clause'] else ''})\n{s['text']}" for s in sources]
    blocks += extra_blocks or []
    with timer.track("llm_ms"):
        return complete(system_prompt(area), user_prompt(question, blocks), temperature=0.1, max_tokens=3500)
