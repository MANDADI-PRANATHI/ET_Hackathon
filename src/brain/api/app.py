"""FastAPI app: serves the mobile chat page and the /ask endpoint.

Run:  make serve   ->  http://localhost:8000
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from brain.copilot.engine import ask

WEB_DIR = Path(__file__).resolve().parents[3] / "web"

app = FastAPI(title="Unified Asset & Operations Brain")


class AskRequest(BaseModel):
    question: str
    role: Optional[str] = None
    k: int = 6


@app.get("/")
def home() -> FileResponse:
    return FileResponse(str(WEB_DIR / "index.html"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask")
def ask_endpoint(req: AskRequest) -> dict:
    return ask(req.question, k=req.k, role=req.role)
