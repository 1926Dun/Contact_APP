"""Assessment engine: log -> structured assessment via LLM."""

import logging

from .knowledge import get_knowledge
from .llm import chat_structured
from .redact import RedactionResult, redact
from .schemas import Assessment

log = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are a crime-recording assessment tool. You analyse police logs against \
Home Office crime-recording rules and produce structured assessments.

You are DECISION SUPPORT — you propose candidate crimes for a trained \
human to review. You never auto-record.

## Recording standard

Apply the BALANCE OF PROBABILITY test from the Home Office Counting Rules \
(HOCR). A crime should be recorded if, on the balance of probability, \
the circumstances as reported amount to a crime defined by law, and there \
is no credible evidence to the contrary.

## Key HOCR principles

{hocr_excerpt}

## NSIR — incident vs crime

{nsir_excerpt}

## Points to prove (master reference)

For each candidate offence, map every point to prove below to the log \
as MET / NOT_MET / UNCLEAR, citing the supporting text from the log.

{points_to_prove}

## Guidance

### Retail robbery alternate offence
{retail_robbery}

### Schools protocol
{schools_protocol}

### NFIB fraud routing
When the log discloses fraud, note that fraud offences are routed to \
NFIB / Action Fraud. Reflect this in the candidate's guidance_applied field.

## Instructions

Given the police log below, produce a structured assessment with:

1. **metadata** — extract reference number, date, time(s), location from \
the log. Leave null if not stated; never guess.

2. **summary** — concise, neutral, factual summary of what happened.

3. **people** — each person mentioned: name/identifier, role \
(victim/suspect/witness), and the basis for that role from the log. \
If ambiguous, say so.

4. **vulnerabilities** — any vulnerability indicators: age, mental health, \
disability, domestic abuse, repeat victimisation, exploitation, etc. \
Each with the indicator name, who it relates to, and supporting detail.

5. **candidates** — every offence the log may disclose:
   - offence_title and legislation
   - classification_code: the Home Office classification code if known \
(format like "001/01", "008/10", etc.)
   - notifiable: true/false if determinable
   - certainty: 0-100 in 10-point increments ONLY (0,10,20...100). \
Driven by the proportion of points to prove clearly met, adjusted for \
how directly the log evidences each one.
   - rationale: reference specific points to prove and the HOCR \
recording standard. Not a vague summary.
   - points_to_prove: list each point with status (met/not_met/unclear) \
and the supporting text from the log.
   - nsir_alternative: if this could be an incident-only recording \
under NSIR, name it.
   - guidance_applied: list any special guidance applied (retail robbery \
alternate, schools protocol, NFIB fraud routing).

Order candidates by certainty, highest first.
"""


def _excerpt_hocr(text: str, max_chars: int = 4000) -> str:
    """Extract key HOCR principles from the full document."""
    lines = text.split("\n")
    key_sections = []
    capture = False
    for line in lines:
        lower = line.lower().strip()
        if any(
            kw in lower
            for kw in [
                "balance of probability",
                "recording standard",
                "principal crime",
                "counting rules",
                "one crime per victim",
                "finished incident",
            ]
        ):
            capture = True
        if capture:
            key_sections.append(line)
            if len("\n".join(key_sections)) > max_chars:
                break
        if capture and line.strip() == "":
            capture = False
    if not key_sections:
        return text[:max_chars]
    return "\n".join(key_sections)[:max_chars]


def _excerpt_nsir(text: str, max_chars: int = 2000) -> str:
    """Extract key NSIR principles."""
    lines = text.split("\n")
    key_sections = []
    capture = False
    for line in lines:
        lower = line.lower().strip()
        if any(
            kw in lower
            for kw in ["incident", "not a crime", "non-crime", "recording"]
        ):
            capture = True
        if capture:
            key_sections.append(line)
            if len("\n".join(key_sections)) > max_chars:
                break
        if capture and line.strip() == "":
            capture = False
    if not key_sections:
        return text[:max_chars]
    return "\n".join(key_sections)[:max_chars]


def build_system_prompt() -> str:
    """Assemble the system prompt from cached knowledge base documents."""
    kb = get_knowledge()
    return SYSTEM_PROMPT_TEMPLATE.format(
        hocr_excerpt=_excerpt_hocr(kb.get("hocr").text),
        nsir_excerpt=_excerpt_nsir(kb.get("nsir").text),
        points_to_prove=kb.get("points_to_prove").text,
        retail_robbery=kb.get("retail_robbery").text,
        schools_protocol=kb.get("schools_protocol").text,
    )


def assess_log(
    log_text: str, use_redaction: bool = False
) -> tuple[Assessment, dict | None]:
    """Run a full assessment on a police log.

    Returns (assessment, redaction_info) where redaction_info is the
    mapping dict if redaction was used, or None otherwise.
    """
    redaction_info = None

    if use_redaction:
        r = redact(log_text)
        send_text = r.redacted_text
        redaction_info = r.to_dict()
        log.info("Redacted %d identifiers before LLM transmission", len(r.mapping))
    else:
        r = None
        send_text = log_text

    system_prompt = build_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Police log:\n\n{send_text}"},
    ]
    assessment = chat_structured(messages, Assessment)

    if r:
        assessment = _deredact_assessment(assessment, r)

    return assessment, redaction_info


def _deredact_assessment(assessment: Assessment, r: RedactionResult) -> Assessment:
    """Replace pseudonyms with original values in the assessment."""
    raw = r.deredact(assessment.model_dump_json())
    return Assessment.model_validate_json(raw)
