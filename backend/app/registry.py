"""Corpus registry: ingestion -> chunking -> embedding -> dual index (Qdrant HNSW + graph adjacency)."""
import json, shutil, threading, time
from pathlib import Path
import numpy as np
from langchain_core.documents import Document
from . import config
from .ingestion.loaders import load_file
from .ingestion.chunker import chunk_documents
from .index import vector
from .index.bm25 import BM25Index
from .index.embeddings import embed_docs
from .graph.extractor import extract
from .graph.store import GraphStore

UPLOADS = config.STORAGE / "uploads"
UPLOADS.mkdir(exist_ok=True, parents=True)
_SRC = config.STORAGE / "sources.json"


class Registry:
    def __init__(self):
        self.chunks: dict[str, Document] = {}
        self.vecs: dict[str, np.ndarray] = {}
        self.bm25 = BM25Index()
        self.graph = GraphStore()
        self.sources: list[dict] = json.loads(_SRC.read_text()) if _SRC.exists() else []
        self.lock = threading.RLock()
        self.last_index = {}
        if self.sources:
            self.reindex()

    # ---- ingestion ----
    def add_file(self, path: Path, practice_area: str | None = None):
        with self.lock:
            self.sources = [s for s in self.sources if s["path"] != str(path)]
            self.sources.append({"path": str(path), "practice_area": practice_area})
            _SRC.write_text(json.dumps(self.sources))

    def add_samples(self):
        for p in sorted(config.SAMPLES.iterdir()):
            if p.suffix.lower() in (".pdf", ".docx", ".json"): self.add_file(p)
        return self.reindex()

    def reindex(self, use_llm: bool = True) -> dict:
        """Full rebuild (corpus is small). Timings reported per pipeline step."""
        with self.lock:
            hp, t = config.HYPERPARAMS, {}
            t0 = time.perf_counter()
            docs = []
            for s in self.sources:
                p = Path(s["path"])
                if p.exists(): docs += load_file(p, s.get("practice_area"))
            t["ingest_ms"] = (time.perf_counter() - t0) * 1000; t0 = time.perf_counter()
            chunks = chunk_documents(docs, hp["chunk_size"], hp["chunk_overlap"])
            t["chunk_ms"] = (time.perf_counter() - t0) * 1000; t0 = time.perf_counter()
            self.chunks = {c.metadata["chunk_id"]: c for c in chunks}
            vecs = embed_docs([c.page_content for c in chunks]) if chunks else []
            self.vecs = {c.metadata["chunk_id"]: np.array(v) for c, v in zip(chunks, vecs)}
            t["embed_ms"] = (time.perf_counter() - t0) * 1000; t0 = time.perf_counter()
            vector.reset(); vector.upsert(chunks)
            self.bm25.build({cid: c.page_content for cid, c in self.chunks.items()})
            t["index_ms"] = (time.perf_counter() - t0) * 1000; t0 = time.perf_counter()
            ex = extract(chunks, use_llm=use_llm)
            self.graph.build(ex, {cid: c.metadata for cid, c in self.chunks.items()})
            t["graph_ms"] = (time.perf_counter() - t0) * 1000
            self.last_index = {"documents": len({c.metadata["doc_id"] for c in chunks}), "chunks": len(chunks),
                               "nodes": self.graph.g.number_of_nodes(), "edges": self.graph.g.number_of_edges(),
                               "embed_model": config.EMBED_MODEL, "timings_ms": {k: round(v) for k, v in t.items()}}
            return self.last_index

    def documents(self) -> list[dict]:
        out: dict[str, dict] = {}
        for c in self.chunks.values():
            m = c.metadata
            d = out.setdefault(m["doc_id"], {"doc_id": m["doc_id"], "filename": m["filename"], "type": m["source_type"],
                                             "practice_area": m["practice_area"], "chunks": 0})
            d["chunks"] += 1
        return list(out.values())

    def remove(self, doc_id: str):
        keep = []
        for s in self.sources:
            p = Path(s["path"])
            if p.exists() and any(c.metadata["doc_id"] == doc_id and c.metadata["filename"] == p.name for c in self.chunks.values()):
                if p.parent == UPLOADS: p.unlink()
                continue
            keep.append(s)
        self.sources = keep; _SRC.write_text(json.dumps(keep))
        return self.reindex()


_reg: Registry | None = None


def get_registry() -> Registry:
    global _reg
    if _reg is None: _reg = Registry()
    return _reg
