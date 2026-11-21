import re
from rank_bm25 import BM25Okapi

_tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())


class BM25Index:
    def __init__(self):
        self.ids: list[str] = []
        self.bm = None

    def build(self, chunk_texts: dict[str, str]):
        self.ids = list(chunk_texts)
        self.bm = BM25Okapi([_tok(t) for t in chunk_texts.values()]) if self.ids else None

    def search(self, q: str, k: int) -> list[tuple[str, float]]:
        if not self.bm: return []
        scores = self.bm.get_scores(_tok(q))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [(self.ids[i], float(scores[i])) for i in order if scores[i] > 0]
