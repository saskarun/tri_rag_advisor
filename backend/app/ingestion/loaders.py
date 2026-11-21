"""Step 1 - Data format & ingestion. Every Document carries provenance metadata."""
import hashlib, json
from pathlib import Path
from langchain_core.documents import Document


def _doc_id(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def _guess_area(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("rbi", "kyc", "pmla", "sebi", "risk", "grc")): return "grc"
    if any(k in n for k in ("spa", "agreement", "deal", "merger", "fema")): return "deals"
    return "tax"


def _load_pdf(path: Path) -> list[Document]:
    try:  # spec: UnstructuredPDFLoader; needs the `unstructured` extra + system deps
        from langchain_community.document_loaders import UnstructuredPDFLoader
        docs = UnstructuredPDFLoader(str(path), mode="single").load()
        for d in docs: d.metadata["page"] = 1
        if any(d.page_content.strip() for d in docs):
            return docs
    except Exception:
        pass
    from pypdf import PdfReader  # fallback parser
    return [Document(page_content=(p.extract_text() or ""), metadata={"page": i + 1})
            for i, p in enumerate(PdfReader(str(path)).pages)]


def _load_docx(path: Path) -> list[Document]:
    from docx import Document as Dx
    text = "\n\n".join(p.text for p in Dx(str(path)).paragraphs if p.text.strip())
    return [Document(page_content=text, metadata={"page": 1})]


def _load_json(path: Path) -> list[Document]:
    data = json.loads(path.read_text())
    rows = data["rows"] if isinstance(data, dict) and "rows" in data else (data if isinstance(data, list) else [data])
    title = data.get("title", path.stem) if isinstance(data, dict) else path.stem
    out = []
    for i, r in enumerate(rows):
        txt = f"{title} - Row {i+1}: " + "; ".join(f"{k}: {v}" for k, v in r.items()) if isinstance(r, dict) else str(r)
        out.append(Document(page_content=txt, metadata={"page": 1, "row": i + 1}))
    return out


def load_file(path: Path, practice_area: str | None = None) -> list[Document]:
    ext = path.suffix.lower()
    loader = {".pdf": _load_pdf, ".docx": _load_docx, ".json": _load_json}.get(ext)
    if not loader:
        raise ValueError(f"Unsupported file type: {ext}")
    docs = loader(path)
    did, area = _doc_id(path), practice_area or _guess_area(path.name)
    for d in docs:
        d.metadata.update(doc_id=did, filename=path.name, source_type=ext.lstrip("."), practice_area=area)
    return [d for d in docs if d.page_content.strip()]
