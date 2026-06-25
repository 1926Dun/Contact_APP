"""Programmatic lookup against the HOCR Principal Crime table (page 14)."""

import pathlib
import re
from functools import lru_cache

_STOPWORDS = frozenset(
    "a an the and or in of with to by on at only including etc".split()
)


def _key_words(text: str) -> frozenset[str]:
    """Normalise text to a set of distinctive words."""
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return frozenset(w for w in words if w not in _STOPWORDS and len(w) > 1)


@lru_cache(maxsize=1)
def _load_tables() -> tuple[dict[str, str], dict[str, str], list[tuple[frozenset[str], str]]]:
    """Return (code_table, hoclass_table, title_lookup).

    code_table    — HO Classification codes ("008/06") → max sentence
    hoclass_table — HO Class strings ("8N") → max sentence
    title_lookup  — [(key_words, max_sentence), ...] sorted most-specific first
    """
    rules_dir = pathlib.Path(__file__).parent.parent.parent / "rules"
    pdfs = list(rules_dir.glob("crime-recording-rules-*.pdf"))
    if not pdfs:
        return {}, {}, []
    import pymupdf
    doc = pymupdf.open(str(pdfs[0]))
    if len(doc) < 14:
        return {}, {}, []
    tabs = doc[13].find_tables()
    if not tabs.tables:
        return {}, {}, []
    return _parse_rows(tabs.tables[0].extract())


def get_table() -> dict[str, str]:
    """Return {classification_code: max_sentence}."""
    return _load_tables()[0]


def _parse_rows(
    rows: list,
) -> tuple[dict[str, str], dict[str, str], list[tuple[frozenset[str], str]]]:
    code_table: dict[str, str] = {}
    hoclass_table: dict[str, str] = {}
    title_lookup: list[tuple[frozenset[str], str]] = []
    last_sentence: str | None = None

    for i, row in enumerate(rows):
        if i < 6:  # skip multi-row header
            continue
        title_cell = (row[0] or "").strip()
        hoclass_cell = (row[1] or "").strip()
        codes_cell = (row[2] or "").strip()
        sentence_cell = (row[3] or "").strip()

        if not codes_cell and not hoclass_cell:
            continue

        if sentence_cell:
            sentence_cell = re.sub(r"(\d+)(yrs?)", r"\1 \2", sentence_cell)
            last_sentence = sentence_cell

        sentence = sentence_cell or last_sentence
        if not sentence:
            continue

        if codes_cell:
            for code in _extract_codes(codes_cell):
                code_table[code] = sentence

        if hoclass_cell:
            for token in re.split(r"[\s,]+", hoclass_cell):
                token = token.strip()
                if token:
                    hoclass_table[token] = sentence

        if title_cell:
            kw = _key_words(title_cell)
            if kw:
                title_lookup.append((kw, sentence))

    # Most-specific (longest) first to avoid spurious subset matches
    title_lookup.sort(key=lambda x: len(x[0]), reverse=True)
    return code_table, hoclass_table, title_lookup


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


def lookup(
    classification_code: str | None, offence_title: str | None = None
) -> tuple[bool, str | None]:
    """Return (is_principal, max_sentence).

    Resolution order:
    1. H.O. Classification code ("008/06")
    2. HO Class string ("8N") — fallback when LLM returns the wrong column
    3. Offence title keyword match — fallback when the code is wrong/missing
    """
    code_table, hoclass_table, title_lookup = _load_tables()

    if classification_code:
        code = classification_code.strip()
        sentence = code_table.get(code) or hoclass_table.get(code)
        if sentence:
            return True, sentence

    if offence_title:
        candidate_words = _key_words(offence_title)
        for table_words, sentence in title_lookup:
            if not table_words:
                continue
            n = len(table_words)
            # Short entries (≤4 words): all must match.
            # Longer entries: allow one miss to absorb table wording variants
            # (e.g. "family/relationship" vs "relationship").
            required = n if n <= 4 else n - 1
            if len(table_words & candidate_words) >= required:
                return True, sentence

    return False, None


def cache_clear() -> None:
    """Clear cached tables (call after knowledge refresh)."""
    _load_tables.cache_clear()
