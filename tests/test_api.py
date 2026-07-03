"""API smoke test — the whole HTTP surface end to end.

Skips cleanly if FastAPI/httpx aren't installed, so the core suite stays runnable
on Level 0 deps. Builds an isolated staging dir so it doesn't depend on generated
data, and points the app at it via STAGING_DIR before import.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from brain.schema import (REGEX, STRUCTURED, Chunk, DocumentRecord, EdgeFact,  # noqa: E402
                          NodeFact, SourceRef, StagedDoc)


def _build_staging(dir_: Path) -> None:
    s = SourceRef(doc_id="reg", path="project_files/asset_register.csv")
    StagedDoc(
        document=DocumentRecord(id="reg", doc_type="ProjectFile", title="Register",
                                path="project_files/asset_register.csv"),
        nodes=[
            NodeFact(label="Asset", key="tag", value="PSV-110B",
                     properties={"tag": "PSV-110B", "name": "Pressure Safety Valve B",
                                 "asset_class": "Valve"}, source=s, confidence=1.0,
                     extractor=STRUCTURED),
            NodeFact(label="Inspection", key="inspection_id", value="INSP-1",
                     properties={"inspection_id": "INSP-1", "type": "Statutory",
                                 "last_inspection_date": "2025-11-06"}, source=s,
                     confidence=1.0, extractor=STRUCTURED),
        ],
        edges=[EdgeFact(type="INSPECTS", from_label="Inspection", from_value="INSP-1",
                        to_label="Asset", to_value="PSV-110B", source=s, confidence=1.0,
                        extractor=STRUCTURED),
               EdgeFact(type="ABOUT", from_label="Document", from_value="reg",
                        to_label="Asset", to_value="PSV-110B", source=s, confidence=1.0,
                        extractor=STRUCTURED)],
        chunks=[Chunk(id="reg::c0", doc_id="reg", ordinal=0,
                      text="PSV-110B pressure safety valve, statutory inspection 2025-11-06.")],
    ).write(dir_)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    _build_staging(staging)
    monkeypatch.setenv("STAGING_DIR", str(staging))
    # Skip loading real transformer models — keeps this suite on Level 0 deps
    # and fast; the local-model code paths are covered by tests/test_offline.py
    # with stubs, and can be exercised for real via `make api`.
    monkeypatch.setenv("SUTRADHAR_SKIP_LOCAL_MODELS", "1")
    import brain.api.app as app_module
    importlib.reload(app_module)          # re-read STAGING_DIR
    from fastapi.testclient import TestClient
    with TestClient(app_module.app) as c:
        yield c


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["assets"] >= 1


def test_ask_returns_cited_answer(client):
    a = client.post("/ask", json={"question": "Is PSV-110B overdue for inspection?",
                                  "role": "safety_officer"}).json()
    assert a["assets"] == ["PSV-110B"]
    assert a["citations"] and a["confidence"] > 0
    assert a["confidence_label"] in {"Low", "Medium", "High"}


def test_compliance_flags_gap(client):
    c = client.get("/compliance").json()
    assert c["summary"]["GAP"] >= 1
    assert any(r["status"] == "GAP" and r["asset"] == "PSV-110B" for r in c["results"])


def test_graph_and_scorecard_and_warnings(client):
    g = client.get("/graph").json()
    assert any(n["hub"] for n in g["nodes"])
    assert len(client.get("/scorecard").json()) == 8
    assert "warnings" in client.get("/warnings").json()


def test_ui_served(client):
    r = client.get("/ui/")
    assert r.status_code == 200 and "Sutradhar" in r.text
