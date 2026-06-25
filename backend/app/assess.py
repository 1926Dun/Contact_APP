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

## HOCR Crime Recording Flowchart (page 11)

For EVERY candidate crime, you MUST trace through these decision steps \
in order and state the outcome of each step in the rationale. This is \
the Home Office mandated decision process:

Step 1 — REPORT: Does the report concern a crime?
  If No → use appropriate NOL closure under NSIR or NCRS where required.

Step 2 — BALANCE OF PROBABILITY: On the balance of probabilities, has \
a notifiable crime been committed?
  If No → record as Crime Related Incident (CRI) if appropriate.

Step 3 — CREDIBLE CONTRARY EVIDENCE: Is there any credible evidence to \
the contrary immediately available?
  If Yes → do not record (but document rationale).

Step 4 — VICTIM TRACEABLE: Can a victim or representative be traced, or \
is it appropriate to record without victim confirmation?
  If No → ensure incident registered and closed as CRI.

Step 5 — VICTIM CONFIRMATION: Does victim or representative confirm as \
a crime, or is it appropriate to record without victim confirmation?
  If No → ensure incident registered and closed as CRI.

Step 6 — ANOTHER FORCE: Is another force recording the crime?
  If Yes → ensure incident registered and closed as CRI.

Step 7 — NCRS/HOCR EXCEPTION: Does NCRS/HOCR direct that a crime \
should not be recorded (e.g. Crime Recording in Schools Protocol)?
  If Yes → do not record as crime.

Step 8 — RECORD AS A CRIME.

Step 9 — AVI CHECK: Is there Additional Verifiable Information (AVI) or \
is the crime to be cancelled or transferred to another force?
  If Yes → re-classify, transfer or cancel in accordance with HOCR.

Step 10 — REMAINS AS RECORDED CRIME → Apply a crime Outcome.

In the rationale for each candidate, explicitly state which flowchart \
steps were applied and their outcome (e.g. "Step 2: On the balance of \
probability, assault is disclosed because..." / "Step 3: No credible \
contrary evidence is available in the log").

## HOCR counting rules (context only — do NOT use to filter candidates)

These rules govern the final *recording count*, not the candidate list. \
Note them in the rationale where relevant, but NEVER suppress a candidate \
because of them.

- ONE CRIME PER VICTIM: counts one recording per victim per offender/group.
- FINISHED INCIDENT RULE: a sequence of crimes reported together counts \
as one recording.
- PRINCIPAL CRIME RULE: if multiple crime types are present, the most \
serious is the principal offence for counting.

The candidate list must include EVERY separately-identifiable offence \
the log may disclose. The human reviewer selects which to record; the \
counting rules inform that decision but are not applied here.

## Key HOCR principles

{hocr_excerpt}

## NSIR — incident vs crime

{nsir_excerpt}

## Principal Crime look-up table (HOCR page 14)

This is the authoritative list of principal crimes. For EVERY candidate offence \
you MUST check whether it appears in this table and set is_principal_crime \
accordingly. Also record the maximum sentence shown in the table \
(e.g. "Life", "10 yrs", "5 yrs") in principal_crime_max_sentence. \
If the offence does NOT appear in this table, set is_principal_crime = false \
and principal_crime_max_sentence = null.

{principal_crime_table}

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

## Vulnerability identification

Use this framework (College of Policing / THRIVE) to assess vulnerability. \
Apply the ABCDE model and look for barriers to disclosure as clues.

{vulnerability_guide}

## Instructions

Given the police log below, produce a structured assessment with:

1. **metadata** — extract reference number, date, time(s), location from \
the log. Leave null if not stated; never guess.

2. **summary** — concise, neutral, factual summary of what happened.

3. **people** — each person mentioned: name/identifier, role \
(victim/suspect/witness), and the basis for that role from the log. \
If ambiguous, say so.

4. **vulnerabilities** — use the ABCDE framework (Appearance, Behaviour, \
Communication, Danger, Environment) and the barriers-to-disclosure clues \
from the Vulnerability Identification Guide above. Look for indicators \
across all vulnerability strands: domestic abuse, stalking, CSE, modern \
slavery, FGM, honour-based abuse, adult/child safeguarding, mental health, \
age, disability, repeat victimisation, exploitation, coercive control, etc. \
Each with the indicator name, who it relates to, and supporting detail \
from the log.

5. **candidates** — EVERY SEPARATELY-IDENTIFIABLE offence the log may \
disclose. Cast wide: include every distinct offence, even lower-certainty \
ones. Do NOT collapse multiple offences into one because they arise from \
the same incident — each offence type is a separate candidate. For example, \
a domestic abuse log may disclose: assault/ABH/GBH (depending on injury \
severity), threats to kill (s.16 OAPA 1861), coercive and controlling \
behaviour (s.76 Serious Crime Act 2015), criminal damage, and others — \
each is a separate candidate. Note HOCR counting rules in the rationale \
where relevant but do not let them suppress any candidate.

   For each candidate include:
   - offence_title and legislation
   - classification_code: the Home Office classification code if known \
(format like "001/01", "008/10", etc.)
   - notifiable: true/false if determinable
   - is_principal_crime: true if the offence appears in the Principal \
Crime look-up table above (HOCR page 14), false otherwise.
   - principal_crime_max_sentence: the maximum sentence from the table \
(e.g. "Life", "10 yrs", "5 yrs") if is_principal_crime is true, else null.
   - certainty: 0-100 in 10-point increments ONLY (0,10,20...100). \
Driven by the proportion of points to prove clearly met, adjusted for \
how directly the log evidences each one.
   - rationale: reference specific points to prove and the HOCR \
recording standard. Not a vague summary. Note any applicable counting \
rule (e.g. principal offence) here, not as a reason to omit this candidate.
   - points_to_prove: list each point with status (met/not_met/unclear) \
and the supporting text from the log.
   - nsir_alternative: if this could be an incident-only recording \
under NSIR, name it.
   - guidance_applied: list any special guidance applied (retail robbery \
alternate, schools protocol, NFIB fraud routing).

Order candidates by certainty, highest first.

6. **counting_rules** — after listing all candidates, explicitly apply each of the three HOCR counting rules to this log:

   - **one_crime_per_victim**: Identify each victim and the offender(s). State how many crimes would be counted under this rule and why (e.g. one victim, one offender group = one crime counted per offence type, but only one recording if the finished incident rule and principal crime rule collapse them).
   - **finished_incident_rule**: State whether the log reports a finished sequence of acts between the same parties reported together in a single report. If yes, state that the sequence counts as one crime for recording purposes. If acts span separate incidents, say so.
   - **principal_crime**: From the candidates above, identify the most serious offence. State which offence it is, why it is the most serious (by reference to the HOCR severity hierarchy or penalty), and that this is the offence that would be recorded as the principal crime.
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


def _extract_principal_crime_table() -> str:
    """Extract the Principal Crime look-up table from page 14 of the HOCR PDF."""
    import pathlib
    import pymupdf

    hocr_path = pathlib.Path(__file__).parent.parent.parent / "rules"
    candidates = list(hocr_path.glob("crime-recording-rules-*.pdf"))
    if not candidates:
        return ""
    doc = pymupdf.open(candidates[0])
    # Page 14 is index 13
    if len(doc) < 14:
        return ""
    return doc[13].get_text()


def build_system_prompt() -> str:
    """Assemble the system prompt from cached knowledge base documents."""
    kb = get_knowledge()
    return SYSTEM_PROMPT_TEMPLATE.format(
        hocr_excerpt=_excerpt_hocr(kb.get("hocr").text),
        nsir_excerpt=_excerpt_nsir(kb.get("nsir").text),
        principal_crime_table=_extract_principal_crime_table(),
        points_to_prove=kb.get("points_to_prove").text,
        retail_robbery=kb.get("retail_robbery").text,
        schools_protocol=kb.get("schools_protocol").text,
        vulnerability_guide=kb.get("vulnerability").text,
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
