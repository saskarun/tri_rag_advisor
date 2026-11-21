"""Steps 5/6 - Dense vector index: Qdrant (embedded local mode), HNSW + cosine."""
import uuid
from langchain_core.documents import Document
from qdrant_client import QdrantClient, models
from .. import config
from .embeddings import embed_docs, embed_query, embed_dim

COLLECTION = "pwc_chunks"
_client: QdrantClient | None = None


def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=str(config.STORAGE / "qdrant"))
    return _client


def reset():
    c = client()
    if c.collection_exists(COLLECTION):
        c.delete_collection(COLLECTION)
    c.create_collection(
        COLLECTION,
        vectors_config=models.VectorParams(size=embed_dim(), distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100),
    )


def upsert(chunks: list[Document]):
    if not chunks: return
    vecs = embed_docs([c.page_content for c in chunks])
    pts = [models.PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.metadata["chunk_id"])), vector=v,
        payload={"text": c.page_content, **c.metadata}) for c, v in zip(chunks, vecs)]
    client().upsert(COLLECTION, pts)


def search_vec(vec: list[float], k: int, allowed_chunk_ids: set[str] | None = None) -> list[tuple[str, float]]:
    c = client()
    if not c.collection_exists(COLLECTION): return []
    flt = None
    if allowed_chunk_ids:
        flt = models.Filter(must=[models.FieldCondition(key="chunk_id", match=models.MatchAny(any=list(allowed_chunk_ids)))])
    res = c.query_points(COLLECTION, query=vec, limit=k, query_filter=flt, with_payload=["chunk_id"]).points
    return [(p.payload["chunk_id"], float(p.score)) for p in res]


def search(query: str, k: int, allowed_chunk_ids=None):
    return search_vec(embed_query(query), k, allowed_chunk_ids)
