"""Programmatic lookup against the HOCR Principal Crime table (page 14)."""

import pathlib
import re
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_tables() -> tuple[dict[str, str], dict[str, str]]:
    """Return (code_table, hoclass_table) from the HOCR page 14 table.

    code_table maps HO Classification codes ("008/06") to max sentence.
    hoclass_table maps HO Class strings ("8N") to max sentence.
    """
    rules_dir = pathlib.Path(__file__).parent.parent.parent / "rules"
    pdfs = list(rules_dir.glob("crime-recording-rules-*.pdf"))
    if not pdfs:
        return {}, {}
    import pymupdf
    doc = pymupdf.open(str(pdfs[0]))
    if len(doc) < 14:
        return {}, {}
    tabs = doc[13].find_tables()
    if not tabs.tables:
        return {}, {}
    return _parse_rows(tabs.tables[0].extract())


def get_table() -> dict[str, str]:
    """Return {classification_code: max_sentence}."""
    return _load_tables()[0]


def _parse_rows(rows: list) -> tuple[dict[str, str], dict[str, str]]:
    code_table: dict[str, str] = {}
    hoclass_table: dict[str, str] = {}
    last_sentence: str | None = None

    for i, row in enumerate(rows):
        if i < 6:  # skip multi-row header
            continue
        hoclass_cell = (row[1] or "").strip()
        codes_cell = (row[2] or "").strip()
        sentence_cell = (row[3] or "").strip()

        if not codes_cell and not hoclass_cell:
            continue

        if sentence_cell:
            # normalise "5yrs" → "5 yrs"
            sentence_cell = re.sub(r"(\d+)(yrs?)", r"\1 \2", sentence_cell)
            last_sentence = sentence_cell

        sentence = sentence_cell or last_sentence
        if not sentence:
            continue

        if codes_cell:
            for code in _extract_codes(codes_cell):
                code_table[code] = sentence

        # Index every whitespace/comma/newline-separated HO Class token (e.g. "8N", "17A-B")
        if hoclass_cell:
            for token in re.split(r"[\s,]+", hoclass_cell):
                token = token.strip()
                if token:
                    hoclass_table[token] = sentence

    return code_table, hoclass_table


def _extract_codes(cell: str) -> list[str]:
    """Expand ranges and comma-separated codes into individual code strings."""
    codes: list[str] = []
    remaining = cell

    range_re = re.compile(r"(\d{3})/(\d{2})\s*[-–]\s*(\d{3})/(\d{2})")
    for m in range_re.finditer(cell):
        prefix, n_start, n_end = m.group(1), int(m.group(2)), int(m.group(4))
        codes.extend(f"{prefix}/{n:02d}" for n in range(n_start, n_end + 1))
        remaining = remaining.replace(m.group(0), " ")

    single_re = re.compile(r"\b(\d{3}/\d{2})\b")
    codes.extend(m.group(1) for m in single_re.finditer(remaining))

    return codes


def lookup(classification_code: str | None) -> tuple[bool, str | None]:
    """Return (is_principal, max_sentence) for a given code or HO Class string.

    Tries the H.O. Classification code ("008/06") first, then falls back to
    the HO Class string ("8N") in case the LLM returns the wrong column.
    """
    if not classification_code:
        return False, None
    code = classification_code.strip()
    code_table, hoclass_table = _load_tables()
    sentence = code_table.get(code) or hoclass_table.get(code)
    return (True, sentence) if sentence else (False, None)


def cache_clear() -> None:
    """Clear cached tables (call after knowledge refresh)."""
    _load_tables.cache_clear()
