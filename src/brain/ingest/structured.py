"""Structured records (CSV/tables) read directly by code — no AI, 100% reliable.
Each handler maps a known file's columns onto ontology entities + relations.
"""
from __future__ import annotations

import csv
from pathlib import Path

from brain.ingest.models import DocFacts, ExtractedEntity, ExtractedRelation


def _rows(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def parse_asset_register(path: Path) -> DocFacts:
    df = DocFacts(path.name, "ProjectFile", str(path))
    for row in _rows(path):
        df.entities.append(ExtractedEntity(
            "Asset", row["tag"],
            {"name": row.get("name"), "asset_class": row.get("asset_class"),
             "manufacturer": row.get("manufacturer"), "criticality": row.get("criticality")},
            source=path.name, method="structured"))
        unit = row.get("unit")
        if unit:
            df.entities.append(ExtractedEntity("Unit", unit, source=path.name, method="structured"))
            df.relations.append(ExtractedRelation(
                "LOCATED_IN", "Asset", row["tag"], "Unit", unit, source=path.name, method="structured"))
    return df


def parse_work_orders(path: Path) -> DocFacts:
    df = DocFacts(path.name, "WorkOrder", str(path))
    for row in _rows(path):
        wo = row["wo_number"]
        df.entities.append(ExtractedEntity(
            "WorkOrder", wo,
            {"action": row.get("action"), "date": row.get("date"), "status": row.get("status")},
            source=path.name, method="structured"))
        df.relations.append(ExtractedRelation(
            "MAINTAINS", "WorkOrder", wo, "Asset", row["asset_tag"], source=path.name, method="structured"))
        person = row.get("performed_by")
        if person:
            df.entities.append(ExtractedEntity("Person", person, source=path.name, method="structured"))
            df.relations.append(ExtractedRelation(
                "PERFORMED", "Person", person, "WorkOrder", wo, source=path.name, method="structured"))
    return df


def parse_inspections(path: Path) -> DocFacts:
    df = DocFacts(path.name, "InspectionReport", str(path))
    for row in _rows(path):
        iid = row["inspection_id"]
        df.entities.append(ExtractedEntity(
            "Inspection", iid,
            {"type": row.get("type"), "last_inspection_date": row.get("last_inspection_date"),
             "result": row.get("result")},
            source=path.name, method="structured"))
        df.relations.append(ExtractedRelation(
            "INSPECTS", "Inspection", iid, "Asset", row["asset_tag"], source=path.name, method="structured"))
    return df


def parse_permits(path: Path) -> DocFacts:
    df = DocFacts(path.name, "Permit", str(path))
    for row in _rows(path):
        pno = row["permit_no"]
        df.entities.append(ExtractedEntity(
            "Permit", pno,
            {"work_type": row.get("work_type"), "issue_date": row.get("issue_date"),
             "status": row.get("status")},
            source=path.name, method="structured"))
        df.relations.append(ExtractedRelation(
            "FOR_WORK_ON", "Permit", pno, "Asset", row["asset_tag"], source=path.name, method="structured"))
    return df


def parse_nonconformances(path: Path) -> DocFacts:
    df = DocFacts(path.name, "NonConformance", str(path))
    for row in _rows(path):
        nid = row["ncr_id"]
        df.entities.append(ExtractedEntity(
            "NonConformance", nid,
            {"finding": row.get("finding"), "raised_date": row.get("raised_date"),
             "status": row.get("status")},
            source=path.name, method="structured"))
        df.relations.append(ExtractedRelation(
            "RAISED_AGAINST", "NonConformance", nid, "Asset", row["asset_tag"],
            source=path.name, method="structured"))
        capa = row.get("capa_id")
        if capa:
            df.entities.append(ExtractedEntity("CAPA", capa, source=path.name, method="structured"))
            df.relations.append(ExtractedRelation(
                "ADDRESSES", "CAPA", capa, "NonConformance", nid, source=path.name, method="structured"))
    return df
