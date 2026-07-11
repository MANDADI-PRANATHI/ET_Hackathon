"""Generate realistic synthetic plant records (the structured part of the corpus):
asset register, work orders, inspections, permits, and non-conformances + CAPAs.

Everything references the same small asset list so it links cleanly in the graph.
One inspection (PSV-110B) is deliberately overdue — that's the gap the Level 4a
compliance checker should catch in the demo.

Every file this writes lives under a `demo/` subfolder inside its category
folder (e.g. data/corpus/work_orders/demo/work_orders.csv, never
data/corpus/work_orders/work_orders.csv directly) — so it can never collide
with or overwrite a real file of the same name, and can be cleanly deleted
later (POST /dev/delete-demo-data, or `rm -rf data/corpus/*/demo`) without
touching anything real. Doc-type routing is unaffected: the router keys off
the top-level category folder, not the exact filename depth.

Run with:  make synth   (or:  python scripts/generate_synthetic.py)
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
DEMO = "demo"   # every corpus write nests under <category>/demo/
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
        CORPUS / "project_files" / DEMO / "asset_register.csv",
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
        CORPUS / "work_orders" / DEMO / "work_orders.csv",
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
        CORPUS / "inspections" / DEMO / "inspections.csv",
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
        CORPUS / "permits" / DEMO / "permits.csv",
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
        CORPUS / "quality_records" / DEMO / "nonconformances.csv",
        ["ncr_id", "asset_tag", "finding", "raised_date", "capa_id", "status"],
        rows,
    )


def _write_text(rel_path: str, content: str) -> None:
    # rel_path is "<category>/<filename>" -- nest under <category>/demo/<filename>.
    category, _, filename = rel_path.partition("/")
    path = CORPUS / category / DEMO / filename
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


def readings() -> bool:
    """Weekly operating readings. P-101A vibration trends UP for weeks before the
    2026-05-18 seal-failure incident (so the RCA agent can connect the dots);
    other assets stay flat as a control. Returns False (and writes nothing) if
    a real readings.csv already exists, so bulk() knows not to append either."""
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
    # readings.csv has no natural "demo/" home -- it's one flat file the RCA
    # agent reads directly (READINGS_FILE), not something routed by folder.
    # Refuse to overwrite it if it already has real content; only ever fill
    # it fresh (missing or empty), so a real deployment's sensor data is
    # never at risk.
    target = ROOT / "data" / "readings" / "readings.csv"
    if target.exists() and target.stat().st_size > 0:
        print(f"  skipped {target.relative_to(ROOT)} (already has data — "
              "not overwriting; delete it yourself first if you want fresh demo readings)")
        return False
    _write(target, ["asset_tag", "parameter", "timestamp", "value", "unit"], rows)
    return True


# =============================================================================
# BULK DATA — a large, realistic plant layered on top of the canonical assets.
# The canonical records above are byte-identical (so the benchmarks stay valid);
# everything below is appended volume so we can stress-test at scale.
# =============================================================================

MANUFACTURERS = ["KSB", "L&T", "Alfa Laval", "Siemens", "Anderson Greenwood",
                 "Emerson", "Flowserve", "Sulzer", "Kirloskar", "BHEL", "Thermax"]
UNITS = ["CDU-1", "CDU-2", "VDU-1", "FCC-1", "HDT-1", "SRU-1", "Utilities", "Tankage"]
REGS = ["OISD-STD-105", "OISD-STD-106", "OISD-STD-116", "29 CFR 1910.119",
        "IS 2062", "IS 4736"]
FAILURES = ["seal failure", "bearing failure", "corrosion", "fatigue crack",
            "overpressure", "high vibration", "gasket leak", "shaft misalignment",
            "tube fouling", "cavitation"]
FINDINGS = ["Inspection overdue", "Procedure not followed", "Out-of-spec reading",
            "Missing record", "Calibration lapsed", "Guard missing", "Corrosion noted"]
ACTIONS_BULK = ["Seal replacement", "Bearing inspection", "Vibration check",
                "Gasket replacement", "Lubrication", "Alignment", "Calibration",
                "Overhaul", "Cleaning", "Valve pop-test"]
PEOPLE_BULK = ["R. Kumar", "S. Patel", "A. Sharma", "M. Iyer", "P. Nair", "K. Rao",
               "D. Mehta", "V. Singh", "N. Reddy", "T. Bose", "G. Menon", "H. Shah",
               "J. Pillai", "L. Verma", "B. Das", "C. Joshi"]
# (class, tag-prefixes)
CLASS_PREFIX = {
    "Pump": ["P", "GA", "PA"], "Valve": ["PSV", "XV", "FV", "PCV", "TV"],
    "Vessel": ["V", "D"], "HeatExchanger": ["E"], "Compressor": ["K", "C"],
    "Instrument": ["FT", "PT", "TT", "LT", "FIC", "PIC"], "Tank": ["TK"],
    "Column": ["T"],
}


def _append(path: pathlib.Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"  +{len(rows)} rows -> {path.relative_to(ROOT)}")


def _build_assets(n: int):
    used = {a[0] for a in ASSETS}
    out = []
    while len(out) < n:
        cls = random.choice(list(CLASS_PREFIX))
        tag = (f"{random.choice(CLASS_PREFIX[cls])}-{random.randint(100, 999)}"
               f"{random.choice(['', '', '', 'A', 'B', 'C'])}")
        if tag in used:
            continue
        used.add(tag)
        out.append((tag, f"{cls} {tag}", cls, random.choice(MANUFACTURERS),
                    random.choice(UNITS), random.choice(["High", "Medium", "Low"])))
    return out


def _bulk_narrative(kind: str, idx: int, assets) -> None:
    a = random.choice(assets)
    tag, _n, _c, _m, unit, _cr = a
    reg = random.choice(REGS)
    who = random.choice(PEOPLE_BULK)
    fail = random.choice(FAILURES)
    d = TODAY - datetime.timedelta(days=random.randint(10, 900))
    if kind == "incident":
        _write_text(f"incidents/INC-{2025}-{500+idx}_{tag}.txt", f"""
INCIDENT INVESTIGATION REPORT
Reference: INC-2025-{500+idx}
Date: {d.isoformat()}
Unit: {unit}

SUMMARY
On {d.isoformat()}, {tag} experienced {fail} during normal operation. The event
was contained and there were no injuries.

ROOT CAUSE
Investigation attributed the {fail} on {tag} to deferred maintenance and a
missed inspection. Relief protection remained within the limits of {reg}.

RECOMMENDATIONS
1. Review the maintenance interval for {tag}.
2. Verify related protective devices per {reg}.
Investigator: {who}
""")
    elif kind == "email":
        _write_text(f"emails/RE_{tag}_{idx}.eml", f"""From: {who} <{who.split()[-1].lower()}@refinery.example>
To: Operations <ops@refinery.example>
Subject: RE: {tag} follow-up on {fail}
Date: {d.strftime('%a, %d %b %Y')} 10:00:00 +0530

Team,

Flagging {fail} observed on {tag} in {unit}. Per {reg} we should schedule a
check. This may relate to the recurring issues we have seen on similar equipment.

Regards,
{who}
""")
    else:  # sop
        setp = random.choice([6, 8, 10, 12, 14, 16])
        _write_text(f"procedures/SOP-{unit}-{200+idx}_{tag}.txt", f"""
STANDARD OPERATING PROCEDURE
SOP-{unit}-{200+idx}: Operation of {tag}
Revision: {random.randint(1,5)}   Effective: {d.isoformat()}

PURPOSE
This procedure governs safe operation of {tag} in unit {unit}.

LIMITS
Maintain within design limits. Overpressure protection is set at {setp} barg in
accordance with {reg}. Do not bypass protective devices while in service.
""")


def bulk(scale: int, assets_all, write_readings: bool = True) -> None:
    print(f"\nGenerating BULK data (scale={scale})...")
    n_assets = scale * 8
    extra = _build_assets(n_assets)
    assets_all.extend(extra)
    _append(CORPUS / "project_files" / DEMO / "asset_register.csv",
            [(t, n, c, m, u, cr) for (t, n, c, m, u, cr) in extra])

    # work orders (bulk) across ALL assets
    n_wo = scale * 80
    tags = [a[0] for a in assets_all]
    wo = []
    for i in range(n_wo):
        d = TODAY - datetime.timedelta(days=random.randint(1, 1400))
        wo.append((f"WO-{20000+i}", random.choice(tags), random.choice(ACTIONS_BULK),
                   d.isoformat(), random.choice(["Completed", "Open", "Closed", "Closed"]),
                   random.choice(PEOPLE_BULK)))
    _append(CORPUS / "work_orders" / DEMO / "work_orders.csv", wo)

    # one inspection per extra asset (valves 6-mo cycle -> some naturally overdue)
    insp = []
    for i, (t, _n, c, _m, _u, _cr) in enumerate(extra):
        d = TODAY - datetime.timedelta(days=random.randint(15, 500))
        insp.append((f"INSP-{20000+i}", t, "Statutory" if c == "Valve" else "Routine",
                     d.isoformat(), random.choice(["Pass", "Pass", "Observation", "Fail"])))
    _append(CORPUS / "inspections" / DEMO / "inspections.csv", insp)

    # permits (bulk)
    n_permit = scale * 15
    ptypes = ["Hot Work", "Confined Space", "Working at Height", "Cold Work", "Electrical"]
    permits_rows = []
    for i in range(n_permit):
        d = TODAY - datetime.timedelta(days=random.randint(0, 120))
        permits_rows.append((f"PTW-{20000+i}", random.choice(tags), random.choice(ptypes),
                             d.isoformat(), random.choice(["Closed", "Active", "Closed"])))
    _append(CORPUS / "permits" / DEMO / "permits.csv", permits_rows)

    # non-conformances + CAPAs (bulk)
    n_ncr = scale * 10
    ncr_rows = []
    for i in range(n_ncr):
        d = TODAY - datetime.timedelta(days=random.randint(5, 800))
        ncr_rows.append((f"NCR-{20000+i}", random.choice(tags), random.choice(FINDINGS),
                        d.isoformat(), f"CAPA-{20000+i}", random.choice(["Open", "Closed"])))
    _append(CORPUS / "quality_records" / DEMO / "nonconformances.csv", ncr_rows)

    # narrative documents (bulk text files -> prose extraction + cross-links)
    n_inc, n_email, n_sop = min(scale, 60), min(scale, 70), min(scale // 2, 40)
    for i in range(n_inc):
        _bulk_narrative("incident", i, extra)
    for i in range(n_email):
        _bulk_narrative("email", i, extra)
    for i in range(n_sop):
        _bulk_narrative("sop", i, extra)
    print(f"  +{n_inc+n_email+n_sop} narrative documents")

    # readings for a subset of assets (some rising -> RCA/warnings signal) --
    # only if readings() actually wrote (i.e. there was no real file to protect).
    if write_readings:
        n_read = min(scale // 2, 40)
        rd = []
        for a in random.sample(extra, min(n_read, len(extra))):
            rising = random.random() < 0.35
            base = random.uniform(2.0, 3.5)
            for wk in range(11):
                ts = datetime.date(2026, 3, 12) + datetime.timedelta(weeks=wk)
                val = base + (wk * random.uniform(0.3, 0.6) if rising else random.uniform(-0.1, 0.1))
                rd.append((a[0], "vibration", ts.isoformat(), round(max(0.5, val), 2), "mm/s"))
        _append(ROOT / "data" / "readings" / "readings.csv", rd)

    print(f"\nTOTAL assets: {len(assets_all)}  ·  bulk work orders: {n_wo}  ·  "
          f"permits: {n_permit}  ·  NCRs: {n_ncr}")


def _get_scale() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--scale", type=int, default=None)
    args, _ = ap.parse_known_args()
    if args.scale is not None:
        return max(0, args.scale)
    return max(0, int(os.environ.get("SCALE", "50")))


def main() -> None:
    scale = _get_scale()
    print("Generating synthetic plant records (canonical demo assets)...")
    asset_register()
    work_orders()
    inspections()
    permits()
    nonconformances()
    narrative_documents()
    wrote_readings = readings()
    if scale > 0:
        bulk(scale, list(ASSETS), write_readings=wrote_readings)
    print(
        "\nDone. (Set SCALE=0 for canonical-only, or SCALE=200 for a huge plant.)"
        "\nAdd real public PDFs to the corpus folders too (see data/corpus/SOURCES.md)."
    )


if __name__ == "__main__":
    main()
