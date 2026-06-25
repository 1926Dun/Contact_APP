# Crime Recording Assessment

Decision-support tool for assessing police logs against Home Office crime-recording rules (HOCR / NSIR).

## What it does

Given a police log, the tool:

1. **Summarises** the log and extracts people (victim, suspect, witness) and vulnerability indicators
2. **Proposes candidate crimes** — every offence the log may disclose, each scored for certainty (0–100) with a rationale tied to the HOCR 10-step decision flowchart and points to prove
3. **Generates an auditable report** — the user selects which crimes to record; the report captures both selected and considered-but-rejected offences with full reasoning and document provenance

The tool proposes; the trained user decides. Nothing is recorded as a crime without an explicit human selection.

## Stack

- **Backend** — Python / FastAPI (`uv`), SQLite, LiteLLM → OpenRouter → Cerebras
- **Frontend** — Vanilla JS / HTML served by FastAPI
- **Documents** — HOCR, NSIR, points-to-prove list, notifiable offence list and guidance loaded at startup from `rules/`, `guidance/`, `reference/`

## Running locally

```bash
# Start backend
cd backend && uv run uvicorn app.main:app --reload

# Or with Docker
docker compose up --build
```

The app is available at `http://localhost:8000`.

Copy `.env.example` to `.env` and set your `OPENROUTER_API_KEY` before starting.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/knowledge` | Loaded documents and their versions/hashes |
| POST | `/api/knowledge/refresh` | Re-ingest documents after an update |
| POST | `/api/assess` | Submit a log (text or file upload) for assessment |
| POST | `/api/reports` | Generate a report from selected candidate crimes |
| GET | `/api/logs` | List assessed logs |
| GET | `/api/logs/{id}` | Retrieve a log and its assessment |
| GET | `/api/reports/{id}` | Retrieve a saved report |

## Source documents

The tool reads crime-recording rules from files in `rules/`, `guidance/`, and `reference/`. These are hot-swappable — replace a file and call `POST /api/knowledge/refresh` to reload without a rebuild. Every assessment records the filename and hash of each document used, so outputs are always traceable to the exact version of the rules.

## Data handling

Police logs contain personal data. Before sending a log to the AI model, you can enable **redaction** to pseudonymise names and identifiers locally; the mapping is held in-process and restored in the response. Review the processing terms of your chosen model provider before using real logs in production.
