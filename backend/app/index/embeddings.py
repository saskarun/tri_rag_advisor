from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings
from .. import config


@lru_cache(maxsize=1)
def get_embedder() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=config.EMBED_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


def embed_dim() -> int:
    return len(get_embedder().embed_query("dim"))


# bge models recommend this instruction prefix for retrieval queries.
def embed_query(q: str):
    if "bge" in config.EMBED_MODEL.lower():
        q = "Represent this sentence for searching relevant passages: " + q
    return get_embedder().embed_query(q)


def embed_docs(texts: list[str]):
    return get_embedder().embed_documents(texts)
