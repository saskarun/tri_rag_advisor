"""Node2Vec-style structural embeddings (biased random walks + PPMI + SVD).
Dependency-free (numpy) stand-in for gensim skip-gram, which has no Python 3.14 wheel."""
import numpy as np
import networkx as nx


def node2vec(g: nx.Graph, dim: int = 32, walk_len: int = 20, walks: int = 10,
             window: int = 4, p: float = 1.0, q: float = 0.5, seed: int = 7) -> dict[str, list[float]]:
    ug = g.to_undirected()
    nodes = list(ug.nodes)
    n = len(nodes)
    if n < 3: return {u: [0.0] * min(dim, max(n, 1)) for u in nodes}
    idx = {u: i for i, u in enumerate(nodes)}
    rng = np.random.default_rng(seed)
    co = np.zeros((n, n))
    for _ in range(walks):
        for start in nodes:
            walk = [start]
            while len(walk) < walk_len:
                cur = walk[-1]; nb = list(ug.neighbors(cur))
                if not nb: break
                if len(walk) == 1: walk.append(nb[rng.integers(len(nb))]); continue
                prev = walk[-2]
                w = np.array([1 / p if x == prev else (1.0 if ug.has_edge(x, prev) else 1 / q) for x in nb])
                walk.append(nb[rng.choice(len(nb), p=w / w.sum())])
            for i, a in enumerate(walk):
                for b in walk[max(0, i - window): i + window + 1]:
                    if a != b: co[idx[a], idx[b]] += 1
    tot = co.sum() or 1.0
    pr, pc = co.sum(1, keepdims=True) / tot, co.sum(0, keepdims=True) / tot
    with np.errstate(divide="ignore", invalid="ignore"):
        ppmi = np.maximum(np.log((co / tot) / (pr @ pc)), 0)
    ppmi = np.nan_to_num(ppmi, neginf=0, posinf=0)
    u, s, _ = np.linalg.svd(ppmi)
    d = min(dim, n - 1)
    emb = u[:, :d] * np.sqrt(s[:d])
    emb /= (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    return {u_: emb[idx[u_]].round(4).tolist() for u_ in nodes}
