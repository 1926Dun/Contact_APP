"""Document ingestion: parse, hash, cache, and serve source documents."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DOCUMENT_MAP = {
    "hocr": {
        "label": "Crime Recording Rules (HOCR)",
        "dir": "rules",
        "glob": "crime-recording-rules-*",
    },
    "nsir": {
        "label": "National Standard for Incident Recording (NSIR)",
        "dir": "rules",
        "glob": "count-nsir11*",
    },
    "retail_robbery": {
        "label": "Alternate Offence for Retail Robbery",
        "dir": "guidance",
        "glob": "alternate-offence-for-retail-robbery*",
    },
    "schools_protocol": {
        "label": "Crime Recording Schools Protocol",
        "dir": "guidance",
        "glob": "crime-recording-schools-protocol*",
    },
    "nfib_fraud": {
        "label": "NFIB Fraud Guidance",
        "dir": "guidance",
        "glob": "nfib-fraud-*",
    },
    "outcomes": {
        "label": "Outcomes Framework Guidance",
        "dir": "guidance",
        "glob": "outcomes-framework-guidance-*",
    },
    "notifiable_list": {
        "label": "Notifiable Offence List",
        "dir": "reference",
        "glob": "notifiable-offence-*",
        "format": "spreadsheet",
    },
    "points_to_prove": {
        "label": "Points to Prove",
        "dir": "reference",
        "glob": "POINTS_TO_PROVE*",
        "format": "markdown",
    },
}


@dataclass
class Document:
    key: str
    label: str
    filename: str
    file_hash: str
    text: str
    pages: int | None = None
    table: list[dict] | None = None


@dataclass
class KnowledgeBase:
    documents: dict[str, Document] = field(default_factory=dict)

    def get(self, key: str) -> Document:
        return self.documents[key]

    def summary(self) -> list[dict]:
        return [
            {
                "key": d.key,
                "label": d.label,
                "filename": d.filename,
                "file_hash": d.file_hash[:16],
                "pages": d.pages,
                "text_length": len(d.text),
                "table_rows": len(d.table) if d.table else None,
            }
            for d in self.documents.values()
        ]


_kb: KnowledgeBase | None = None


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_file(directory: str, glob_pattern: str) -> Path:
    search_dir = PROJECT_ROOT / directory
    # Match pdf, docx, xlsx, ods, md
    candidates = sorted(search_dir.glob(f"{glob_pattern}.*")) + sorted(
        search_dir.glob(glob_pattern)
    )
    # Filter to supported extensions
    supported = {".pdf", ".docx", ".xlsx", ".ods", ".md"}
    candidates = [c for c in candidates if c.suffix.lower() in supported]
    if not candidates:
        raise FileNotFoundError(
            f"Missing source document: no file matching '{glob_pattern}' "
            f"in {search_dir}"
        )
    return candidates[0]


def _parse_pdf(path: Path) -> tuple[str, int]:
    doc = pymupdf.open(path)
    pages = len(doc)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text, pages


def _parse_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_spreadsheet(path: Path) -> tuple[str, list[dict]]:
    suffix = path.suffix.lower()
    if suffix == ".ods":
        df = pd.read_excel(path, engine="odf", header=1)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, header=1)
    else:
        raise ValueError(f"Unsupported spreadsheet format: {suffix}")
    # Drop fully-empty columns and rows
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    # Filter to current offences only
    if "Current" in df.columns:
        df = df[df["Current"] == "Y"]
    records = df.to_dict(orient="records")
    text = df.to_string(index=False)
    return text, records


def _ingest_document(key: str, spec: dict) -> Document:
    path = _find_file(spec["dir"], spec["glob"])
    fmt = spec.get("format")
    fhash = _file_hash(path)

    if fmt == "markdown":
        text = _parse_markdown(path)
        return Document(
            key=key, label=spec["label"], filename=path.name,
            file_hash=fhash, text=text,
        )
    elif fmt == "spreadsheet":
        text, table = _parse_spreadsheet(path)
        return Document(
            key=key, label=spec["label"], filename=path.name,
            file_hash=fhash, text=text, table=table,
        )
    else:
        text, pages = _parse_pdf(path)
        return Document(
            key=key, label=spec["label"], filename=path.name,
            file_hash=fhash, text=text, pages=pages,
        )


def load_knowledge() -> KnowledgeBase:
    """Parse all source documents. Raises FileNotFoundError on any missing file."""
    global _kb
    docs = {}
    errors = []
    for key, spec in DOCUMENT_MAP.items():
        try:
            docs[key] = _ingest_document(key, spec)
        except FileNotFoundError as e:
            errors.append(str(e))
    if errors:
        raise FileNotFoundError(
            "Missing source documents:\n" + "\n".join(errors)
        )
    _kb = KnowledgeBase(documents=docs)
    return _kb


def get_knowledge() -> KnowledgeBase:
    """Return the cached knowledge base, loading if needed."""
    global _kb
    if _kb is None:
        return load_knowledge()
    return _kb


def refresh_knowledge() -> KnowledgeBase:
    """Re-ingest all source documents."""
    return load_knowledge()
