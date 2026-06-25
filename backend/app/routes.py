import json
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .assess import assess_log
from .db import get_db
from .knowledge import get_knowledge, refresh_knowledge
from .report import generate_report
from .schemas import Assessment, ReportRequest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class AssessTextRequest(BaseModel):
    text: str


class LogResponse(BaseModel):
    id: int
    source: str
    filename: str | None
    text: str
    created_at: str


@router.get("/knowledge")
async def knowledge_status():
    """Return loaded source documents with versions and hashes."""
    kb = get_knowledge()
    return {"documents": kb.summary()}


@router.post("/knowledge/refresh")
async def knowledge_refresh():
    """Re-ingest source documents after a Home Office update."""
    kb = refresh_knowledge()
    return {"documents": kb.summary(), "refreshed": True}


async def _store_and_assess(content: str, source: str, filename: str | None):
    """Store the log, run assessment, store result, return both."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO logs (source, filename, text) VALUES (?, ?, ?)",
        (source, filename, content),
    )
    log_id = cursor.lastrowid
    await db.commit()

    row = await db.execute("SELECT * FROM logs WHERE id = ?", (log_id,))
    log_row = dict(await row.fetchone())

    log.info("Running assessment for log %d", log_id)
    assessment = assess_log(content)

    result_json = assessment.model_dump_json()
    await db.execute(
        "INSERT INTO assessments (log_id, result_json) VALUES (?, ?)",
        (log_id, result_json),
    )
    await db.commit()
    await db.close()

    return {
        "log": log_row,
        "assessment": assessment.model_dump(),
    }


@router.post("/assess")
async def assess_file(file: UploadFile = File(None), text: str = Form(None)):
    """Accept a police log as uploaded .txt file or pasted text."""
    if file and file.filename:
        if not file.filename.endswith(".txt"):
            raise HTTPException(400, "Only .txt files are supported")
        content = (await file.read()).decode("utf-8")
        source = "file"
        filename = file.filename
    elif text:
        content = text
        source = "paste"
        filename = None
    else:
        raise HTTPException(400, "Provide either a file upload or text")

    content = content.strip()
    if not content:
        raise HTTPException(400, "Log is empty")

    return await _store_and_assess(content, source, filename)


@router.post("/assess/json")
async def assess_json(body: AssessTextRequest):
    """Accept a police log as JSON body (pasted text)."""
    content = body.text.strip()
    if not content:
        raise HTTPException(400, "Log is empty")

    return await _store_and_assess(content, "paste", None)


@router.get("/logs", response_model=list[LogResponse])
async def list_logs():
    db = await get_db()
    rows = await db.execute("SELECT * FROM logs ORDER BY created_at DESC")
    logs = [dict(r) for r in await rows.fetchall()]
    await db.close()
    return logs


@router.get("/logs/{log_id}")
async def get_log(log_id: int):
    db = await get_db()
    row = await db.execute("SELECT * FROM logs WHERE id = ?", (log_id,))
    log_row = await row.fetchone()
    if not log_row:
        await db.close()
        raise HTTPException(404, "Log not found")
    log_data = dict(log_row)

    arow = await db.execute(
        "SELECT result_json FROM assessments WHERE log_id = ?", (log_id,)
    )
    assessment_row = await arow.fetchone()
    await db.close()

    result = {"log": log_data}
    if assessment_row:
        result["assessment"] = json.loads(assessment_row["result_json"])
    return result


@router.post("/reports")
async def create_report(body: ReportRequest):
    """Generate a report from user's crime selections."""
    db = await get_db()

    arow = await db.execute(
        "SELECT result_json FROM assessments WHERE log_id = ?", (body.log_id,)
    )
    assessment_row = await arow.fetchone()
    if not assessment_row:
        await db.close()
        raise HTTPException(404, "Assessment not found for this log")

    assessment = Assessment.model_validate_json(assessment_row["result_json"])

    if any(i < 0 or i >= len(assessment.candidates) for i in body.selected_indices):
        await db.close()
        raise HTTPException(400, "Invalid candidate index")

    report = generate_report(body.log_id, assessment, body.selected_indices)
    report_json = report.model_dump_json()

    cursor = await db.execute(
        "INSERT INTO reports (log_id, report_json) VALUES (?, ?)",
        (body.log_id, report_json),
    )
    await db.commit()
    report_id = cursor.lastrowid
    await db.close()

    result = report.model_dump()
    result["id"] = report_id
    return result


@router.get("/reports/{report_id}")
async def get_report(report_id: int):
    """Retrieve a saved report."""
    db = await get_db()
    row = await db.execute(
        "SELECT id, log_id, report_json, created_at FROM reports WHERE id = ?",
        (report_id,),
    )
    report_row = await row.fetchone()
    await db.close()
    if not report_row:
        raise HTTPException(404, "Report not found")
    result = json.loads(report_row["report_json"])
    result["id"] = report_row["id"]
    return result


@router.delete("/logs/{log_id}")
async def delete_log(log_id: int):
    db = await get_db()
    row = await db.execute("SELECT id FROM logs WHERE id = ?", (log_id,))
    if not await row.fetchone():
        await db.close()
        raise HTTPException(404, "Log not found")
    await db.execute("DELETE FROM reports WHERE log_id = ?", (log_id,))
    await db.execute("DELETE FROM assessments WHERE log_id = ?", (log_id,))
    await db.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    await db.commit()
    await db.close()
    return {"deleted": log_id}
