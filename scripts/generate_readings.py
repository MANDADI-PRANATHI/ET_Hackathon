"""Generate a simulated sensor-readings feed (temperature, vibration, pressure)
for each asset over the last 60 days. A real plant feed (OPC-UA / MQTT) would
plug into the same 'readings adapter'; this CSV is the demo stand-in.

A rising-vibration anomaly is deliberately planted on P-101B so the RCA agent
has a real failure signal to investigate.

  python scripts/generate_readings.py     (or: make readings)
"""
from __future__ import annotations

import csv
import datetime
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "readings" / "readings.csv"
TODAY = datetime.date(2026, 6, 24)
DAYS = 60
random.seed(7)

ASSETS = ["P-101A", "P-101B", "V-204", "E-301", "C-102", "PSV-110A", "PSV-110B", "FT-150"]
# metric -> (baseline, noise, unit)
METRICS = {
    "temperature": (65.0, 2.0, "degC"),
    "vibration": (2.2, 0.25, "mm/s"),
    "pressure": (8.0, 0.2, "bar"),
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for tag in ASSETS:
        for metric, (base, noise, unit) in METRICS.items():
            for d in range(DAYS, 0, -1):
                day = TODAY - datetime.timedelta(days=d)
                value = base + random.gauss(0, noise)
                # Planted anomaly: P-101B vibration climbs over the last 30 days.
                if tag == "P-101B" and metric == "vibration" and d <= 30:
                    value += (30 - d) * 0.08
                rows.append((tag, day.isoformat(), metric, round(value, 2), unit))

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["asset_tag", "date", "metric", "value", "unit"])
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} readings, {len(ASSETS)} assets)")
    print("Planted anomaly: P-101B vibration rises over the last 30 days.")


if __name__ == "__main__":
    main()
