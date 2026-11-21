"""LLM-guided entity-relation extraction with a deterministic rule-based fallback."""
import json, re
from concurrent.futures import ThreadPoolExecutor
from langchain_core.documents import Document
from .. import config
from .normalizer import ALIASES

TYPES = ["Authority", "Law", "Organization", "Obligation", "Control", "Penalty", "Threshold", "Concept"]
SYS = ("You extract a compliance knowledge graph from regulatory text. Return ONLY JSON: "
       '{"entities":[{"name":str,"type":str}],"relations":[{"source":str,"relation":str,"target":str}]}. '
       f"Types: {', '.join(TYPES)}. Relations are short snake_case verbs (e.g. supervises, parent_of, maps_to, "
       "imposes_penalty, applies_to, customer_of, indemnifies, governed_by). Use exact names from the text; "
       "do not split a legal clause; max 12 entities.")

_CACHE = config.STORAGE / "extraction_cache.json"


def _llm_extract(text: str) -> dict:
    from ..llm import complete
    raw = complete(SYS, text, temperature=0.0, max_tokens=3000)
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0))


_ORG = re.compile(r"\b([A-Z][\w&.]*(?:\s+[A-Z][\w&.]*)*\s+(?:Ltd\.?|Limited|Pvt\.? Ltd\.?|Bank Ltd\.?|Partners|Industries Ltd\.?))")
_LAW = re.compile(r"((?:Section|Rule)\s+\d+[A-Za-z]*(?:\([\w]+\))*(?:\([\w]+\))?(?:\s+of\s+the\s+[A-Z][\w ,]+?(?:Act|Rules)(?:,?\s*\d{4})?)?)")
_CTRL = re.compile(r"(Control\s+C-\d+\s*\([^)]*\))")
_PEN = re.compile(r"(penalty[^.]{0,60}?INR\s*[\d,]+(?:\s*to\s*INR\s*[\d,]+)?)", re.I)


def _rule_extract(text: str) -> dict:
    ents: dict[str, str] = {}
    low = text.lower()
    for canon, al in ALIASES.items():
        if any(re.search(rf"\b{re.escape(a)}\b", low) for a in al):
            ents[canon] = "Authority" if canon in ("CBDT (Income Tax Dept)", "CBIC", "RBI", "FIU-IND", "GST Council") else \
                          "Law" if "Act" in canon or canon in ("PMLA", "FEMA") else "Concept"
    for m in _ORG.findall(text): ents[m.strip().rstrip(".")] = "Organization"
    for m in _LAW.findall(text): ents[m.strip()] = "Law"
    for m in _CTRL.findall(text): ents[m] = "Control"
    for m in _PEN.findall(text): ents[m.strip()] = "Penalty"
    names = list(ents)
    rels = []
    for s in re.split(r"(?<=[.;])\s+", text):
        here = [n for n in names if n.lower() in s.lower() or any(a in s.lower() for a in ALIASES.get(n, []))]
        for i, a in enumerate(here):
            for b in here[i + 1:]:
                rel = "maps_to" if "maps to" in s else "parent_of" if "parent of" in s else \
                      "customer_of" if "customer of" in s else "supervises" if "supervise" in s else \
                      "imposes_penalty" if ents[b] == "Penalty" or ents[a] == "Penalty" else "related_to"
                rels.append({"source": a, "relation": rel, "target": b})
    return {"entities": [{"name": n, "type": t} for n, t in ents.items()], "relations": rels}


def extract(chunks: list[Document], use_llm: bool = True, workers: int = 4) -> dict[str, dict]:
    cache = json.loads(_CACHE.read_text()) if _CACHE.exists() else {}
    mode = "llm" if (use_llm and config.OPENROUTER_API_KEY) else "rule"

    def one(c: Document):
        key = f"{mode}:{c.metadata['chunk_id']}:{hash(c.page_content) & 0xffffff}"
        if key in cache: return c.metadata["chunk_id"], cache[key]
        try:
            r = _llm_extract(c.page_content) if mode == "llm" else _rule_extract(c.page_content)
        except Exception:
            r = _rule_extract(c.page_content)
        cache[key] = r
        return c.metadata["chunk_id"], r

    with ThreadPoolExecutor(workers) as ex:
        out = dict(ex.map(one, chunks))
    _CACHE.write_text(json.dumps(cache))
    return out
