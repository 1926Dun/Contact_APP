# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Crime Recording Assessment App

## Overview

This is a decision-support web app for **assessing police logs against Home Office crime-recording rules**. It reads a log, summarises it, extracts the people involved, flags vulnerability, and proposes the crimes that may need recording — each scored for certainty with a written rationale — so a trained decision-maker can confirm the right classification.

It is **decision support, not the decision-maker.** The app proposes; the user disposes. Nothing is recorded as a crime without an explicit human selection, and every proposal, selection, and rejection is captured for audit.

The app runs in two phases:

**Phase 1 — Assess.** Given a log, the app returns:

1. A plain-English **summary** of the log.
2. **Victims, suspects, and witnesses**, each named with the role it has been assigned and the basis for that assignment.
3. **Vulnerabilities** — indicators present in the log (age, mental health, disability, domestic abuse, repeat victimisation, exploitation, etc.).
4. **Candidate crimes** — every offence the log may disclose, scored **0–100 in 10-point increments** by certainty, ordered most-certain first, each with a rationale tied to the points to prove.

**Phase 2 — Select & report.** The user reviews the candidate crimes and selects the ones they agree with. The app then produces a **report** containing the log's key details, the summary, the people, the **crimes selected** (with rationale), and the **crimes considered but not selected** (with rationale). The report is the auditable record of the decision.

## Source documents (single source of truth)

These files are the authoritative knowledge base for what counts as a crime and how it is recorded. **Read and parse them at startup**, structure them, and cache them. Do **not** hardcode their contents in code, and do **not** invent a rule, offence, or point to prove if a document is missing — **fail loudly** with a clear message naming the missing file.

```
rules/
  crime-recording-rules-2026_27-April-v2.<pdf|docx>   # HOCR — the authority for what is a recordable crime
  count-nsir11.<pdf|docx>                              # NSIR — National Standard for Incident Recording
guidance/
  alternate-offence-for-retail-robbery.<pdf|docx>
  crime-recording-schools-protocol.<pdf|docx>
  nfib-fraud-april-2026.<pdf|docx>                     # NFIB / Action Fraud routing for fraud offences
  outcomes-framework-guidance-2026.<pdf|docx>          # outcome codes / disposal framework
reference/
  notifiable-offence-and-notifiable-reported-incidents-april-2026.<xlsx|ods>   # the canonical notifiable list
  point-to-prove-list-2026.<pdf|docx>                  # offences with their points to prove (also see POINTS_TO_PROVE.md at project root)
```


**These documents change.** The Home Office reissues them (typically annually, sometimes mid-year). The app must treat them as **hot-swappable**:

- Do not bake any version's content into code. All rules, offence definitions, points to prove, notifiable status, and outcome codes are read from the files at runtime.
- Detect the loaded version per document (filename, file hash, and any internal version/date string) and **surface it in the UI and in every report**, so an assessment is always traceable to the exact documents that produced it.
- Provide a way to re-ingest after a document is replaced (`POST /api/knowledge/refresh`) without a rebuild.

### How each document is used

- **crime-recording-rules (HOCR)** — the test for whether something is a recordable crime, the principal-offence / counting decisions, and the "balance of probability" recording standard.
- **count-nsir11 (NSIR)** — where a log is a recordable *incident* rather than a crime; used to flag non-crime / incident-only dispositions.
- **point-to-prove-list** — for each candidate offence, the elements that must be present. **This drives the certainty score** (see below).
- **notifiable-offence … .xlsx** — cross-reference every candidate against the canonical list; attach the Home Office classification code and notifiable flag where present.
- **alternate-offence-for-retail-robbery** — apply the alternate-offence guidance when a retail incident presents as robbery but records differently.
- **crime-recording-schools-protocol** — apply the schools protocol when the log involves a school setting.
- **nfib-fraud-april-2026** — route fraud offences correctly (NFIB / Action Fraud) and reflect that in the candidate's recording rationale.
- **outcomes-framework-guidance** — where relevant, note the applicable outcome framing for a selected crime.

## Assessment output (what the model must produce)

A single structured object per log:

- **Log metadata** — log/reference number, date, time(s), location if stated. Extracted from the log text; left null (not guessed) if absent.
- **Summary** — concise, neutral, factual.
- **People** — a list, each with: name/identifier, role (`victim` | `suspect` | `witness`), and the basis for that role from the log. A person may appear once; if the log is ambiguous, say so rather than forcing a role.
- **Vulnerabilities** — each with the indicator, who it relates to, and the supporting detail from the log.
- **Candidate crimes** — see scoring below.

### Certainty scoring

For every candidate offence, map each **point to prove** (from `point-to-prove-list`) to the log as **met / not met / unclear**, citing the supporting text. The **certainty score is driven by that mapping**, expressed **0–100 in 10-point increments only** (`0, 10, 20 … 100`):

- Roughly, the proportion of points to prove that are clearly met, adjusted for how directly the log evidences each one. All points clearly met and offence squarely within the HOCR test → high (90–100). Key element missing or contradicted → low. Genuinely indeterminate → mid-band with the uncertainty named.
- Each candidate carries a **rationale** that references the specific points to prove and the HOCR recording standard — not a vague summary.
- Each candidate also carries: legislation/offence title, **notifiable flag + Home Office classification code** (from the xlsx), any **NSIR incident-only** alternative, and any guidance applied (retail-robbery alternate, schools protocol, NFIB fraud routing).
- Candidates are returned **ordered by certainty, highest first**.

The score is a confidence signal for the human reviewer; it never auto-selects or auto-records.

## Report (phase 2 output)

After the user selects the crimes they agree with, generate a report containing:

- **Log details** — number, date, time(s), location (as captured).
- **Summary.**
- **People** — victims, suspects, witnesses.
- **Crimes selected** — each with offence title, legislation, classification code, notifiable status, and the rationale (points to prove met).
- **Crimes considered but not selected** — each retained candidate with its certainty score and the rationale, including why it falls away.
- **Provenance footer** — the version/hash of every source document used, and a timestamp.

Persist the report and make it exportable. The "considered but not selected" section is deliberate: it shows the reasoning was applied and rejected, which is what an audit or supervisor review needs.

## AI design

- **Gateway: OpenRouter.** All model calls go through OpenRouter's OpenAI-compatible Chat Completions endpoint. Base URL, API key, and model are set in `.env` (`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `MODEL`). The model is swappable without code changes.
- **Provider: Cerebras.** Pin Cerebras as the serving provider via OpenRouter's provider routing (`provider.only = ["Cerebras"]`) for fast, long-context grounded reasoning. Keep the provider list configurable in `.env` so a fallback provider can be added without code changes. Optionally support a **direct Cerebras path** (`api.cerebras.ai`, also OpenAI-compatible) selected by an `LLM_ROUTE=openrouter|cerebras` switch — same client interface either way.
- **Structured output.** Define Pydantic schemas for the assessment object and the report. Request **strict JSON** via `response_format` (json_schema) where the served model supports it; otherwise instruct JSON-only and **validate with Pydantic, re-prompting once on a parse/validation failure.** Never regex over prose.
- **Grounding.** The system prompt is assembled at runtime from the cached source documents, so the rules, points to prove, notifiable list, and outcome codes always reflect the **current** files. Pass the relevant slices (e.g. the points to prove for plausible offences) rather than the whole corpus where context allows.
- **Two prompt paths.** *Assess* (log → structured assessment) and *Report* (log + user selections → structured report). Keep them separate and small.
- **Determinism.** Low temperature for scoring and classification; the goal is consistency, not creativity.
- **LLM integration pattern.** See `SKILL.md` for the concrete LiteLLM + OpenRouter code pattern (imports, `completion()` calls, structured output via `response_format`). Use that as the implementation reference.

## Technical design

- Backend in `backend/` — a **`uv`** project using **FastAPI**.
- Frontend in `frontend/`. A statically built frontend served by FastAPI is fine if it keeps the stack simple.
- Database: **SQLite** — persist logs, assessments, candidate crimes, user selections, and reports, with the source-document versions attached to each assessment. This is the audit trail.
- Package the project into a **Docker** container.
- Backend available at `http://localhost:8000`.

### Expected commands (once scaffold is built)

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload    # dev server
cd backend && uv run pytest                            # all tests
cd backend && uv run pytest tests/test_foo.py::test_bar  # single test

# Docker
docker compose up --build
```

Scripts in `scripts/`:

```
# Mac
scripts/start-mac.sh
scripts/stop-mac.sh
# Linux
scripts/start-linux.sh
scripts/stop-linux.sh
# Windows
scripts/start-windows.ps1
scripts/stop-windows.ps1
```

## API endpoints

- `GET  /api/health` — health check.
- `GET  /api/knowledge` — loaded source documents with their detected versions/hashes (for the UI provenance panel).
- `POST /api/knowledge/refresh` — re-ingest the source documents after a Home Office update; no rebuild required.
- `POST /api/assess` — body: the log (pasted text or uploaded file). Returns the structured assessment (metadata, summary, people, vulnerabilities, scored candidate crimes).
- `POST /api/reports` — body: `log_id` + selected candidate ids. Returns the report (selected + considered-but-not-selected).
- `GET  /api/logs` — list assessed logs.
- `GET  /api/logs/{id}` — retrieve a log and its assessment.
- `DELETE /api/logs/{id}` — delete a log and its assessment.
- `GET  /api/reports/{id}` — retrieve a saved report.

## Colour scheme

(Shared with the Promotion App so the two tools look like one family.)

- Police Navy: `#0a2342` (headings)
- Authority Blue: `#1c5d99` (primary)
- Elevation Gold: `#c8a24b` (accent)
- Action Teal: `#2a9d8f` (submit/confirm buttons)
- Slate Text: `#4a4a4a`
- Certainty bands: red → amber → green for low → mid → high certainty.

## Data handling & governance

Police logs contain personal and often special-category data. Because model calls leave the machine (OpenRouter / Cerebras), treat this as a live data-protection consideration, not an afterthought:

- Confirm the processing terms and retention posture of the chosen route before any real log is sent; prefer zero-retention / no-training options, and keep a production path open to an in-tenant route (e.g. Azure) if external processing is not acceptable.
- Support **redaction / pseudonymisation** of names and identifiers before transmission, with the mapping held locally.
- Keep the **audit trail** complete: store the model's candidates and rationale, the user's selections and rejections, the source-document versions, and timestamps. This supports both crime-recording assurance and the DP accountability principle.
- Surface a clear, non-removable reminder in the UI that the output is decision support and the recording decision rests with the trained user.

## .env variable naming

The `.env` currently uses `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` (pointing at OpenRouter). The spec above references `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `MODEL`. Align variable names during scaffold setup — the `.env` is the source of truth for what exists, the spec above is the target naming.

## VERY IMPORTANT

- Be simple. Approach tasks in a simple, incremental way.
- Work incrementally ALWAYS. Small, simple steps. Validate and check each increment before moving on.
- Use LATEST APIs as of NOW.

## MANDATORY code style

- Do not overengineer. Do not program defensively. Use exception handlers only when needed.
- Identify root cause before fixing issues. Prove with evidence, then fix.
- Work incrementally with small steps. Validate each increment.
- Use latest library APIs.
- Use **`uv`** as the Python package manager. Always `uv run xxx`, never `python3 xxx`. Always `uv add xxx`, never `pip install xxx`.
- Favour clear, concise docstring comments. Be sparing with comments outside docstrings.
- Favour short modules, short methods and functions. Name things clearly.
- Never use emojis in code, print statements, or logging.
- Keep `README.md` concise.

## Important — debugging and fixing

- When troubleshooting, ALWAYS identify the root cause BEFORE fixing.
- Reproduce consistently.
- PROVE THE PROBLEM FIRST — don't guess.
- Try one test at a time. Be methodical.
- Don't jump to conclusions. Don't apply workarounds.

## Development process

When instructed to build a feature:

1. Implement the smallest vertical slice that delivers it end to end.
2. Validate the increment before moving on.
3. Add unit tests for the scoring/classification logic and integration tests for the API.
4. Run and fix until green.
5. Keep this `CLAUDE.md` Implementation Status updated.

## Implementation status

Suggested build order:

- [x] Project scaffold: Docker, FastAPI (`uv`) backend, frontend, start/stop scripts, `/api/health`.
- [x] Document ingestion: parse rules/guidance/reference files (pdf, docx, **xlsx/ods**); structure and cache; version/hash detection; `/api/knowledge`, `/api/knowledge/refresh`. Fail loudly on a missing file.
- [x] LLM client: OpenRouter gateway with Cerebras provider pinning; `.env` config; Pydantic structured output with one re-prompt on validation failure.
- [x] Assessment engine: log ingestion, summary, people extraction, vulnerability flags, points-to-prove mapping, certainty scoring, notifiable cross-reference; `/api/assess`.
- [x] Selection + report: candidate selection model, report generation (selected + considered), provenance footer; `/api/reports`.
- [x] Persistence: SQLite for logs, assessments, selections, reports + document versions; `/api/logs` CRUD, `/api/reports/{id}`.
- [ ] Data handling: optional redaction/pseudonymisation before transmission; audit-trail completeness.
- [ ] UI: paste/upload log → assessment view (summary, people, vulnerabilities, scored candidates) → select crimes → report view with provenance, ordered by certainty.
