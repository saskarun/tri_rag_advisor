"""Step 2 - Semantic chunking. Clause-aware, token-based RecursiveCharacterTextSplitter."""
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from .tokenizer import get_tokenizer, count_tokens, MAX_TOKENS

# Try to break at legal-clause boundaries before generic paragraph/sentence breaks.
CLAUSE_SEPARATORS = [r"\n(?=Section \d)", r"\n(?=Clause \d)", r"\n(?=Rule \d)", "\n\n", "\n", ". ", " ", ""]
CLAUSE_RE = re.compile(r"^\s*((?:Section|Clause|Rule|Article)\s+[\w.()-]+)", re.I | re.M)


def make_splitter(size: int, overlap: int) -> RecursiveCharacterTextSplitter:
    size = min(size, MAX_TOKENS - 2)  # leave room for [CLS]/[SEP]
    return RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        get_tokenizer(), chunk_size=size, chunk_overlap=overlap,
        separators=CLAUSE_SEPARATORS, is_separator_regex=True, keep_separator=True)


def _normalize_clauses(text: str) -> str:
    # Put each clause on its own line so the separators above can see it.
    return re.sub(r"\s+(?=(?:Section|Clause|Rule)\s+\d+\.)", "\n", text)


def chunk_documents(docs: list[Document], size: int, overlap: int) -> list[Document]:
    sp, out = make_splitter(size, overlap), []
    for d in docs:
        parts = sp.split_text(_normalize_clauses(d.page_content))
        for i, p in enumerate(parts):
            m = CLAUSE_RE.search(p)
            meta = dict(d.metadata, chunk_index=i, clause=m.group(1) if m else None, n_tokens=count_tokens(p))
            meta["chunk_id"] = f"{meta['doc_id']}-p{meta.get('page', 1)}-{i}"
            out.append(Document(page_content=p.strip(), metadata=meta))
    return out
