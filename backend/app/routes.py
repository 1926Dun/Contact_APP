from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .db import get_db

router = APIRouter(prefix="/api")


class AssessTextRequest(BaseModel):
    text: str


class LogResponse(BaseModel):
    id: int
    source: str
    filename: str | None
    text: str
    created_at: str


@router.post("/assess", response_model=LogResponse)
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

    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO logs (source, filename, text) VALUES (?, ?, ?)",
        (source, filename, content),
    )
    await db.commit()
    row = await db.execute("SELECT * FROM logs WHERE id = ?", (cursor.lastrowid,))
    log = await row.fetchone()
    await db.close()
    return dict(log)


@router.post("/assess/json", response_model=LogResponse)
async def assess_json(body: AssessTextRequest):
    """Accept a police log as JSON body (pasted text)."""
    content = body.text.strip()
    if not content:
        raise HTTPException(400, "Log is empty")

    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO logs (source, filename, text) VALUES (?, ?, ?)",
        ("paste", None, content),
    )
    await db.commit()
    row = await db.execute("SELECT * FROM logs WHERE id = ?", (cursor.lastrowid,))
    log = await row.fetchone()
    await db.close()
    return dict(log)


@router.get("/logs", response_model=list[LogResponse])
async def list_logs():
    db = await get_db()
    rows = await db.execute("SELECT * FROM logs ORDER BY created_at DESC")
    logs = [dict(r) for r in await rows.fetchall()]
    await db.close()
    return logs


@router.get("/logs/{log_id}", response_model=LogResponse)
async def get_log(log_id: int):
    db = await get_db()
    row = await db.execute("SELECT * FROM logs WHERE id = ?", (log_id,))
    log = await row.fetchone()
    await db.close()
    if not log:
        raise HTTPException(404, "Log not found")
    return dict(log)


@router.delete("/logs/{log_id}")
async def delete_log(log_id: int):
    db = await get_db()
    row = await db.execute("SELECT id FROM logs WHERE id = ?", (log_id,))
    if not await row.fetchone():
        await db.close()
        raise HTTPException(404, "Log not found")
    await db.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    await db.commit()
    await db.close()
    return {"deleted": log_id}
