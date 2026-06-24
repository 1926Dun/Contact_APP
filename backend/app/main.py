from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import logging

from .db import init_db
from .knowledge import load_knowledge
from .routes import router

log = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    kb = load_knowledge()
    log.info(
        "Knowledge base loaded: %d documents",
        len(kb.documents),
    )
    yield


app = FastAPI(title="Crime Recording Assessment App", lifespan=lifespan)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
