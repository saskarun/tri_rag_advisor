import networkx as nx
from app.rag.fusion import rrf
from app.graph.normalizer import canonical
from app.graph.store import GraphStore
from app.graph.node2vec import node2vec
from app.eval.kpis import _norm


def test_rrf_math_and_order():
    r = dict(rrf([["a", "b"], ["b", "c"]], alpha=60))
    assert abs(r["b"] - (1 / 62 + 1 / 61)) < 1e-9
    assert max(r, key=r.get) == "b"


def test_alias_normalization():
    assert canonical("CBDT") == canonical("Income Tax Dept") == canonical("Tax Authority")
    k = {}
    assert canonical("Meridian Industries Ltd.", k) == canonical("Meridian Industries Limited", k)


def _store():
    s = GraphStore()
    for n, c in [("A", "c1"), ("B", "c2"), ("C", "c3"), ("D", "c4")]:
        s.g.add_node(n, type="Concept", aliases={n}, chunks={c}, docs={"d"})
    s.g.add_edge("A", "B", relation="r", chunks={"c1"}); s.g.add_edge("B", "C", relation="r", chunks={"c2"}); s.g.add_edge("C", "D", relation="r", chunks={"c3"})
    return s


def test_khop_radius_and_blocking():
    s = _store()
    assert set(s.khop(["A"], 2)["nodes"]) == {"A", "B", "C"}
    assert set(s.khop(["A"], 1)["nodes"]) == {"A", "B"}
    assert "C" not in s.khop(["A"], 3, blocked_nodes={"B"})["nodes"]
    assert "C" not in s.khop(["A"], 3, blocked_edges={("B", "C")})["nodes"]


def test_node2vec_shape():
    g = nx.path_graph(6)
    e = node2vec(g, dim=4)
    assert len(e) == 6 and len(e[0]) == 4


def test_chunker_respects_size_and_clauses():
    from app.ingestion.chunker import chunk_documents
    from app.ingestion.tokenizer import count_tokens
    from langchain_core.documents import Document
    text = "\n".join(f"Clause {i}. " + "The Seller shall indemnify the Buyer against losses. " * 12 for i in range(1, 9))
    ch = chunk_documents([Document(page_content=text, metadata={"doc_id": "x", "page": 1})], 200, 20)
    assert len(ch) > 1 and all(count_tokens(c.page_content) <= 205 for c in ch)
    assert all(c.metadata["clause"] for c in ch[:1])


def test_fact_matching_normalization():
    assert _norm("INR 5 crore") in _norm("exceeding  INR 5 crore.")
