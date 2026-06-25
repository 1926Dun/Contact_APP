"""Extract text from uploaded log files (.txt, .pdf, .docx)."""

import io

import docx
import pymupdf

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from a file based on its extension."""
    ext = _get_extension(filename)

    if ext == ".txt":
        return data.decode("utf-8")
    elif ext == ".pdf":
        return _extract_pdf(data)
    elif ext == ".docx":
        return _extract_docx(data)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def is_supported(filename: str) -> bool:
    return _get_extension(filename) in SUPPORTED_EXTENSIONS


def _get_extension(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _extract_pdf(data: bytes) -> str:
    doc = pymupdf.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def _extract_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)
