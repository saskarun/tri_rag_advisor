"""Step 5/6 - Graph adjacency index: Entity -[Relation]-> Target, with chunk back-references.
NetworkX is the working copy; Neo4j (GRAPH_BACKEND=neo4j) mirrors writes and serves k-hop via Cypher."""
import json, os, re
import networkx as nx
from .. import config
from .normalizer import canonical, ALIASES, org_key
from .node2vec import node2vec

_FILE = config.STORAGE / "graph.json"


class GraphStore:
    def __init__(self):
        self.g = nx.MultiDiGraph()
        self.backend = config.GRAPH_BACKEND

    # ---- build ----
    def clear(self):
        self.g = nx.MultiDiGraph()

    def build(self, extracted: dict[str, dict], chunk_meta: dict[str, dict]):
        self.clear()
        known: dict[str, str] = {}
        links = []  # (raw, canonical) pairs for entity-resolution accuracy
        for cid, r in extracted.items():
            raw2c = {}
            for e in r.get("entities", []):
                name, c = e["name"], canonical(e["name"], known)
                raw2c[name] = c; links.append((name, c))
                if c not in self.g:
                    self.g.add_node(c, type=e.get("type", "Concept"), aliases=set(), chunks=set(), docs=set())
                self.g.nodes[c]["aliases"].add(name)
                self.g.nodes[c]["chunks"].add(cid)
                self.g.nodes[c]["docs"].add(chunk_meta[cid]["filename"])
            for rel in r.get("relations", []):
                s = raw2c.get(rel["source"]) or canonical(rel["source"], known)
                t = raw2c.get(rel["target"]) or canonical(rel["target"], known)
                if s == t: continue
                for n in (s, t):
                    if n not in self.g:
                        self.g.add_node(n, type="Concept", aliases={n}, chunks={cid}, docs={chunk_meta[cid]["filename"]})
                if not any(d.get("relation") == rel["relation"] and cid in d["chunks"] for d in (self.g.get_edge_data(s, t) or {}).values()):
                    self.g.add_edge(s, t, relation=rel["relation"], chunks={cid})
        self.links = links
        emb = node2vec(self.g)
        for n, v in emb.items(): self.g.nodes[n]["emb"] = v
        self.save()
        if self.backend == "neo4j": self._mirror_neo4j()

    # ---- query ----
    def match_nodes(self, query: str) -> list[str]:
        q = query.lower()
        hits = []
        for n, d in self.g.nodes(data=True):
            names = {n.lower(), org_key(n), *(a.lower() for a in d["aliases"]), *(org_key(a) for a in d["aliases"]), *ALIASES.get(n, [])}
            if any(len(a) > 2 and re.search(rf"\b{re.escape(a)}\b", q) for a in names): hits.append(n)
        return hits

    def khop(self, seeds: list[str], k: int, blocked_nodes: set[str] | None = None,
             blocked_edges: set[tuple[str, str]] | None = None) -> dict:
        """BFS over the undirected view up to k hops. Returns visited nodes, paths, supporting chunk ids."""
        blocked_nodes, blocked_edges = blocked_nodes or set(), blocked_edges or set()
        seen = {s: 0 for s in seeds if s in self.g and s not in blocked_nodes}
        paths, frontier = [], list(seen)
        for depth in range(1, k + 1):
            nxt = []
            for u in frontier:
                for v in set(self.g.successors(u)) | set(self.g.predecessors(u)):
                    if v in blocked_nodes or (u, v) in blocked_edges or (v, u) in blocked_edges: continue
                    for a, b in ((u, v), (v, u)):
                        if (a, b) in blocked_edges: continue
                        for d in (self.g.get_edge_data(a, b) or {}).values():
                            paths.append({"source": a, "relation": d["relation"], "target": b, "hop": depth})
                    if v not in seen: seen[v] = depth; nxt.append(v)
            frontier = nxt
        chunks: dict[str, int] = {}
        for n, depth in seen.items():
            for cid in self.g.nodes[n]["chunks"]: chunks[cid] = min(chunks.get(cid, 9), depth)
        for p in paths:
            for d in (self.g.get_edge_data(p["source"], p["target"]) or {}).values():
                for cid in d["chunks"]: chunks[cid] = min(chunks.get(cid, 9), p["hop"])
        return {"nodes": seen, "paths": paths, "chunks": chunks}

    # ---- export / persistence ----
    def to_json(self) -> dict:
        nodes = [{"id": n, "type": d["type"], "aliases": sorted(d["aliases"]), "docs": sorted(d["docs"]),
                  "degree": self.g.degree(n)} for n, d in self.g.nodes(data=True)]
        edges = [{"id": f"{u}|{v}|{k}", "source": u, "target": v, "relation": d["relation"]}
                 for u, v, k, d in self.g.edges(keys=True, data=True)]
        return {"nodes": nodes, "edges": edges}

    def save(self):
        data = {"nodes": [[n, {**d, "aliases": sorted(d["aliases"]), "chunks": sorted(d["chunks"]), "docs": sorted(d["docs"])}] for n, d in self.g.nodes(data=True)],
                "edges": [[u, v, {**d, "chunks": sorted(d["chunks"])}] for u, v, d in self.g.edges(data=True)],
                "links": getattr(self, "links", [])}
        _FILE.write_text(json.dumps(data))

    def load(self):
        if not _FILE.exists(): return
        data = json.loads(_FILE.read_text())
        self.clear()
        for n, d in data["nodes"]:
            self.g.add_node(n, **{**d, "aliases": set(d["aliases"]), "chunks": set(d["chunks"]), "docs": set(d["docs"])})
        for u, v, d in data["edges"]:
            self.g.add_edge(u, v, **{**d, "chunks": set(d["chunks"])})
        self.links = [tuple(x) for x in data.get("links", [])]

    def _mirror_neo4j(self):
        from neo4j import GraphDatabase
        drv = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
        with drv.session() as s:
            s.run("MATCH (n:Entity) DETACH DELETE n")
            for n, d in self.g.nodes(data=True):
                s.run("MERGE (e:Entity {name:$n}) SET e.type=$t, e.chunks=$c", n=n, t=d["type"], c=sorted(d["chunks"]))
            for u, v, d in self.g.edges(data=True):
                s.run("MATCH (a:Entity {name:$u}),(b:Entity {name:$v}) MERGE (a)-[r:REL {relation:$r}]->(b) SET r.chunks=$c",
                      u=u, v=v, r=d["relation"], c=sorted(d["chunks"]))
        drv.close()
