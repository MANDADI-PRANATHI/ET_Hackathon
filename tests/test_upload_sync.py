"""Live-onboarding endpoints — /upload, /sync, and the asset timeline.

The point of these tests: a document added while the API is running must be
queryable immediately (no restart, no rebuild step), and syncing the corpus
folder must only re-read what actually changed. All offline — the upload path
uses the deterministic extractors only.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from brain.schema import (STRUCTURED, Chunk, DocumentRecord, EdgeFact,  # noqa: E402
                          NodeFact, SourceRef, StagedDoc)


def _build_staging(dir_: Path) -> None:
    s = SourceRef(doc_id="reg", path="project_files/asset_register.csv")
    StagedDoc(
        document=DocumentRecord(id="reg", doc_type="ProjectFile", title="Register",
                                path="project_files/asset_register.csv"),
        nodes=[
            NodeFact(label="Asset", key="tag", value="PSV-110B",
                     properties={"tag": "PSV-110B", "asset_class": "Valve"},
                     source=s, confidence=1.0, extractor=STRUCTURED),
            NodeFact(label="Inspection", key="inspection_id", value="INSP-1",
                     properties={"inspection_id": "INSP-1", "type": "Statutory",
                                 "last_inspection_date": "2025-11-06",
                                 "result": "Passed"},
                     source=s, confidence=1.0, extractor=STRUCTURED),
            NodeFact(label="WorkOrder", key="wo_number", value="WO-501",
                     properties={"wo_number": "WO-501", "action": "Seal replaced",
                                 "date": "2025-05-02", "status": "Closed"},
                     source=s, confidence=1.0, extractor=STRUCTURED),
        ],
        edges=[EdgeFact(type="INSPECTS", from_label="Inspection", from_value="INSP-1",
                        to_label="Asset", to_value="PSV-110B", source=s,
                        confidence=1.0, extractor=STRUCTURED),
               EdgeFact(type="MAINTAINS", from_label="WorkOrder", from_value="WO-501",
                        to_label="Asset", to_value="PSV-110B", source=s,
                        confidence=1.0, extractor=STRUCTURED)],
        chunks=[Chunk(id="reg::c0", doc_id="reg", ordinal=0,
                      text="PSV-110B pressure safety valve, statutory inspection 2025-11-06.")],
    ).write(dir_)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _build_staging(staging)
    monkeypatch.setenv("STAGING_DIR", str(staging))
    monkeypatch.setenv("CORPUS_DIR", str(corpus))
    import brain.api.app as app_module
    importlib.reload(app_module)          # re-read STAGING_DIR / CORPUS_DIR
    from fastapi.testclient import TestClient
    with TestClient(app_module.app) as c:
        yield c


def test_timeline_is_chronological_with_sources(client):
    t = client.get("/assets/PSV-110B/timeline").json()
    kinds = [(e["date"], e["kind"]) for e in t["events"]]
    assert kinds == [("2025-05-02", "WorkOrder"), ("2025-11-06", "Inspection")]
    assert all(e["source"] for e in t["events"])


def test_asset_summary_reports_records_and_risks_from_facts(client):
    s = client.get("/assets/PSV-110B/summary").json()
    assert s["records"] == {"Inspection": 1, "WorkOrder": 1}
    assert s["last_activity"] == "2025-11-06"
    # PSV-110B's inspection is overdue relative to today -> a real, computed risk.
    assert s["status"] == "Needs attention"
    assert any("Compliance gap" in r for r in s["open_risks"])
    assert client.get("/assets/NOPE-999/summary").status_code == 404


def test_timeline_unknown_asset_is_empty_not_error(client):
    t = client.get("/assets/NOPE-999/timeline").json()
    assert t["events"] == []


def test_upload_makes_document_queryable_immediately(client):
    body = b"Work order note: replaced bearing on pump P-777 on 2026-06-01."
    r = client.post("/upload?filename=note.txt&folder=work_orders", content=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "P-777" in d["assets_linked"]
    # The brain refreshed in place: the new asset is visible with no restart.
    tags = [a["value"] for a in client.get("/assets").json()["assets"]]
    assert "P-777" in tags
    ans = client.post("/ask", json={"question": "What happened to P-777?"}).json()
    assert "P-777" in ans["assets"]


def test_upload_rejects_bad_folder_and_unreadable_file(client):
    r = client.post("/upload?filename=x.txt&folder=nonsense", content=b"hi")
    assert r.status_code == 400
    r = client.post("/upload?filename=x.zip&folder=work_orders", content=b"\x00\x01")
    assert r.status_code == 415


def test_sync_ingests_only_new_and_changed_files(client, tmp_path):
    inc = tmp_path / "corpus" / "incidents"
    inc.mkdir(parents=True, exist_ok=True)
    (inc / "trip.txt").write_text(
        "Incident: compressor K-301 tripped on high vibration.", encoding="utf-8")
    d1 = client.post("/sync").json()
    assert len(d1["ingested"]) == 1
    tags = [a["value"] for a in client.get("/assets").json()["assets"]]
    assert "K-301" in tags
    # Second sync: nothing changed, nothing re-read.
    d2 = client.post("/sync").json()
    assert d2["ingested"] == []
    assert d2["unchanged"] >= 1
