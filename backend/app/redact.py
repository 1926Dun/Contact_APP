"""Redaction/pseudonymisation of names and identifiers before LLM transmission."""

import re


TITLE_PATTERN = re.compile(
    r"\b(Mr|Mrs|Ms|Miss|Dr|Det|Sgt|PC|Insp|Supt)\b\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+[A-Z]{2,})?)",
)

ALLCAPS_NAME_PATTERN = re.compile(
    r"\b([A-Z]{2,}(?:\s+[A-Z]{2,})*)\b"
)

ALLCAPS_EXCLUDE = {
    "CCTV", "UK", "NHS", "CPS", "DNA", "ID", "NFIB", "NSIR", "HOCR", "ASBO",
    "GBH", "ABH", "DV", "MH", "DA", "NFA", "RTC", "IP", "DP", "PNC",
    "ANPR", "BMW", "VW", "LOG", "AM", "PM", "SVRO", "DOB", "CAD",
}

PHONE_PATTERN = re.compile(
    r"\b(0\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}|\+44\s?\d[\s\d]{9,12})\b"
)

POSTCODE_PATTERN = re.compile(
    r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.IGNORECASE
)

DOB_PATTERN = re.compile(
    r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})\b"
)


class RedactionResult:
    def __init__(self, redacted_text: str, mapping: dict[str, str]):
        self.redacted_text = redacted_text
        self.mapping = mapping

    def deredact(self, text: str) -> str:
        result = text
        for pseudonym, original in self.mapping.items():
            result = result.replace(pseudonym, original)
        return result

    def to_dict(self) -> dict:
        return {"redacted_text": self.redacted_text, "mapping": self.mapping}


def redact(text: str) -> RedactionResult:
    """Replace names and identifiers with pseudonyms, return mapping."""
    mapping = {}
    counters = {"PERSON": 0, "PHONE": 0, "POSTCODE": 0, "DOB": 0}
    result = text

    # Names with titles (e.g. "Mrs Janet SMITH")
    for match in TITLE_PATTERN.finditer(text):
        full = match.group(0)
        if full in mapping.values():
            continue
        pseudonym = _find_pseudonym(mapping, full)
        if not pseudonym:
            counters["PERSON"] += 1
            pseudonym = f"[PERSON_{counters['PERSON']}]"
            mapping[pseudonym] = full
        result = result.replace(full, pseudonym)

    # Standalone all-caps words (likely surnames in police logs)
    for match in ALLCAPS_NAME_PATTERN.finditer(result):
        word = match.group(1)
        if word in ALLCAPS_EXCLUDE or len(word) < 3:
            continue
        if any(word in v for v in mapping.values()):
            continue
        if word.startswith("[") or word.startswith("PERSON"):
            continue
        pseudonym = _find_pseudonym(mapping, word)
        if not pseudonym:
            counters["PERSON"] += 1
            pseudonym = f"[PERSON_{counters['PERSON']}]"
            mapping[pseudonym] = word
        result = result.replace(word, pseudonym)

    # Phone numbers
    for match in PHONE_PATTERN.finditer(result):
        phone = match.group(1)
        counters["PHONE"] += 1
        pseudonym = f"[PHONE_{counters['PHONE']}]"
        mapping[pseudonym] = phone
        result = result.replace(phone, pseudonym)

    # Postcodes
    for match in POSTCODE_PATTERN.finditer(result):
        pc = match.group(1)
        counters["POSTCODE"] += 1
        pseudonym = f"[POSTCODE_{counters['POSTCODE']}]"
        mapping[pseudonym] = pc
        result = result.replace(pc, pseudonym)

    # Dates of birth
    for match in DOB_PATTERN.finditer(result):
        dob = match.group(1)
        counters["DOB"] += 1
        pseudonym = f"[DOB_{counters['DOB']}]"
        mapping[pseudonym] = dob
        result = result.replace(dob, pseudonym)

    return RedactionResult(redacted_text=result, mapping=mapping)


def _find_pseudonym(mapping: dict[str, str], value: str) -> str | None:
    """Check if this value (or a substring) already has a pseudonym."""
    for pseudonym, original in mapping.items():
        if value in original or original in value:
            return pseudonym
    return None
