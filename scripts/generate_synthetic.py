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


def _write_text(rel_path: str, content: str) -> None:
    path = CORPUS / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def narrative_documents() -> None:
    """A few realistic prose documents that weave the assets into a story.

    These give the graph cross-functional links no single table holds — e.g. an
    incident narrative and an email that both point at the overdue PSV-110B,
    connecting maintenance, safety, and compliance. They also exercise the
    prose-extraction (AI) and regex paths, not just the structured readers.
    """
    # Incident report (prose -> failure modes, causal links, reg reference).
    _write_text(
        "incidents/INC-2026-014_P-101A_seal_failure.txt",
        """
INCIDENT INVESTIGATION REPORT
Reference: INC-2026-014
Date: 2026-05-18
Unit: CDU-1

SUMMARY
On 2026-05-18, crude feed pump P-101A tripped on high vibration and was found
with a failed mechanical seal, releasing a small quantity of hydrocarbon to the
bund. There were no injuries. Standby pump P-101B was started and feed was
maintained.

ROOT CAUSE
The mechanical seal failure was caused by shaft misalignment introduced during
the seal replacement recorded under a recent work order. Vibration readings on
P-101A had been trending upward for three weeks before the trip but were not
actioned, indicating a gap in the vibration-monitoring routine.

SAFETY SYSTEMS
Pressure safety valve PSV-110A on the associated vessel V-204 lifted correctly
and reseated. The relief protection remained within the requirements of
OISD-STD-105.

RECOMMENDATIONS
1. Re-check alignment on P-101A after every seal replacement.
2. Restore the vibration-monitoring routine on all crude feed pumps.
3. Review the overdue statutory inspection on PSV-110B (see NCR raised by QA).
Investigator: A. Sharma
""",
    )

    # Email thread (prose -> the compliance gap discussed across departments).
    _write_text(
        "emails/RE_PSV-110B_inspection.eml",
        """From: S. Patel <s.patel@refinery.example>
To: R. Kumar <r.kumar@refinery.example>
Cc: M. Iyer <m.iyer@refinery.example>
Subject: RE: PSV-110B statutory inspection overdue
Date: Mon, 22 Jun 2026 09:14:00 +0530

Ravi,

QA flagged during the internal audit that the statutory inspection on PSV-110B
is overdue. Our records show the last inspection was in November 2025, and the
6-month cycle required under OISD-STD-105 has clearly lapsed.

This is the same valve called out in the P-101A incident (INC-2026-014) last
month. We should schedule the pop-test before the next audit window and raise a
CAPA so it is not missed again.

Can maintenance book a slot this week?

Thanks,
Suresh
""",
    )

    # Operating procedure (prose -> procedure governs asset + a parameter).
    _write_text(
        "procedures/SOP-CDU-021_V-204_level_control.txt",
        """
STANDARD OPERATING PROCEDURE
SOP-CDU-021: Reflux Drum V-204 Level Control
Revision: 3   Effective: 2026-01-10

PURPOSE
This procedure governs safe operation of reflux drum V-204 in unit CDU-1.

NORMAL OPERATION
Maintain V-204 level between 40% and 70%. The high-level alarm setpoint is 80%.
If level exceeds the high-high setpoint of 90%, the feed flow measured by flow
transmitter FT-150 must be reduced manually.

RELIEF PROTECTION
Overpressure protection for V-204 is provided by pressure safety valves PSV-110A
and PSV-110B, set at 12 barg in accordance with OISD-STD-105. Do not isolate a
relief valve while the drum is in service.
""",
    )


def readings() -> None:
    """Weekly operating readings. P-101A vibration trends UP for weeks before the
    2026-05-18 seal-failure incident (so the RCA agent can connect the dots);
    other assets stay flat as a control."""
    rows = []
    # P-101A vibration rising 2.4 -> 7.2 mm/s over 10 weeks up to the trip.
    start = datetime.date(2026, 3, 12)
    vib = 2.4
    for wk in range(11):
        ts = start + datetime.timedelta(weeks=wk)
        rows.append(("P-101A", "vibration", ts.isoformat(), round(vib, 2), "mm/s"))
        rows.append(("P-101A", "bearing_temp", ts.isoformat(),
                     round(58 + wk * 1.3, 1), "degC"))
        vib += 0.48
    # P-101B (standby) stays healthy/flat.
    for wk in range(11):
        ts = start + datetime.timedelta(weeks=wk)
        rows.append(("P-101B", "vibration", ts.isoformat(),
                     round(2.3 + (wk % 3) * 0.1, 2), "mm/s"))
    READINGS = ROOT / "data" / "readings"
    _write(READINGS / "readings.csv",
           ["asset_tag", "parameter", "timestamp", "value", "unit"], rows)


def main() -> None:
    print("Generating synthetic plant records...")
    asset_register()
    work_orders()
    inspections()
    permits()
    nonconformances()
    narrative_documents()
    readings()
    print(
        "\nDone. Add real public PDFs to the remaining corpus folders "
        "(see data/corpus/SOURCES.md)."
    )


if __name__ == "__main__":
    main()
