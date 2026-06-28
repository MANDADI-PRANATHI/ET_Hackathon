"""Generate realistic synthetic plant records (the structured part of the corpus):
asset register, work orders, inspections, permits, and non-conformances + CAPAs.

Everything references the same small asset list so it links cleanly in the graph.
One inspection (PSV-110B) is deliberately overdue — that's the gap the Level 4a
compliance checker should catch in the demo.

Run with:  make synth   (or:  python scripts/generate_synthetic.py)
"""
from __future__ import annotations

import csv
import datetime
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
TODAY = datetime.date(2026, 6, 24)
random.seed(42)

# (tag, name, asset_class, manufacturer)
ASSETS = [
    ("P-101A", "Crude Feed Pump A", "Pump", "KSB"),
    ("P-101B", "Crude Feed Pump B", "Pump", "KSB"),
    ("V-204", "Reflux Drum", "Vessel", "L&T"),
    ("E-301", "Crude Preheat Exchanger", "HeatExchanger", "Alfa Laval"),
    ("C-102", "Recycle Gas Compressor", "Compressor", "Siemens"),
    ("PSV-110A", "Pressure Safety Valve A", "Valve", "Anderson Greenwood"),
    ("PSV-110B", "Pressure Safety Valve B", "Valve", "Anderson Greenwood"),
    ("FT-150", "Feed Flow Transmitter", "Instrument", "Emerson"),
]
PEOPLE = ["R. Kumar", "S. Patel", "A. Sharma", "M. Iyer"]


def _write(path: pathlib.Path, header, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


def asset_register() -> None:
    rows = [
        (t, n, c, m, "CDU-1", random.choice(["High", "Medium", "Low"]))
        for (t, n, c, m) in ASSETS
    ]
    _write(
        CORPUS / "project_files" / "asset_register.csv",
        ["tag", "name", "asset_class", "manufacturer", "unit", "criticality"],
        rows,
    )


def work_orders() -> None:
    actions = [
        "Seal replacement", "Bearing inspection", "Vibration check",
        "Gasket replacement", "Lubrication", "Alignment",
    ]
    rows = []
    for i in range(1, 31):
        tag = random.choice(ASSETS)[0]
        date = TODAY - datetime.timedelta(days=random.randint(5, 700))
        rows.append((
            f"WO-{4400 + i}", tag, random.choice(actions),
            date.isoformat(), random.choice(["Completed", "Open", "Closed"]),
            random.choice(PEOPLE),
        ))
    _write(
        CORPUS / "work_orders" / "work_orders.csv",
        ["wo_number", "asset_tag", "action", "date", "status", "performed_by"],
        rows,
    )


def inspections() -> None:
    rows = []
    for i, (tag, _n, cls, _m) in enumerate(ASSETS, start=1):
        # Valves are on a 6-month statutory cycle. Make PSV-110B overdue (~230 days).
        days_ago = 230 if tag == "PSV-110B" else random.randint(20, 170)
        last = TODAY - datetime.timedelta(days=days_ago)
        rows.append((
            f"INSP-{200 + i}", tag,
            "Statutory" if cls == "Valve" else "Routine",
            last.isoformat(), random.choice(["Pass", "Pass", "Observation"]),
        ))
    _write(
        CORPUS / "inspections" / "inspections.csv",
        ["inspection_id", "asset_tag", "type", "last_inspection_date", "result"],
        rows,
    )


def permits() -> None:
    types = ["Hot Work", "Confined Space", "Working at Height", "Cold Work"]
    rows = []
    for i in range(1, 11):
        tag = random.choice(ASSETS)[0]
        date = TODAY - datetime.timedelta(days=random.randint(0, 60))
        rows.append((
            f"PTW-{700 + i}", tag, random.choice(types),
            date.isoformat(), random.choice(["Closed", "Active", "Closed"]),
        ))
    _write(
        CORPUS / "permits" / "permits.csv",
        ["permit_no", "asset_tag", "work_type", "issue_date", "status"],
        rows,
    )


def nonconformances() -> None:
    findings = [
        "Inspection overdue", "Procedure not followed",
        "Out-of-spec reading", "Missing record",
    ]
    rows = []
    for i in range(1, 9):
        tag = random.choice(ASSETS)[0]
        date = TODAY - datetime.timedelta(days=random.randint(10, 400))
        rows.append((
            f"NCR-{50 + i}", tag, random.choice(findings),
            date.isoformat(), f"CAPA-{50 + i}", random.choice(["Open", "Closed"]),
        ))
    _write(
        CORPUS / "quality_records" / "nonconformances.csv",
        ["ncr_id", "asset_tag", "finding", "raised_date", "capa_id", "status"],
        rows,
    )


def main() -> None:
    print("Generating synthetic plant records...")
    asset_register()
    work_orders()
    inspections()
    permits()
    nonconformances()
    print(
        "\nDone. Add real public PDFs to the remaining corpus folders "
        "(see data/corpus/SOURCES.md)."
    )


if __name__ == "__main__":
    main()
