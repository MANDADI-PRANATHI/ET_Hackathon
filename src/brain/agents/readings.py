"""The 'readings adapter' — reads recent equipment readings and detects trends
with plain code (no AI). For the demo it reads the CSV feed; a real plant feed
(OPC-UA / MQTT / a time-series DB) would implement the same load function.
"""
from __future__ import annotations

import csv
import pathlib
import statistics
from typing import Any, Dict, List

DEFAULT_PATH = "data/readings/readings.csv"


def load_readings(asset_tag: str, path: str = DEFAULT_PATH) -> List[Dict[str, str]]:
    p = pathlib.Path(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["asset_tag"] == asset_tag]


def summarize(asset_tag: str, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    rows = load_readings(asset_tag, path)
    by_metric: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        by_metric.setdefault(r["metric"], []).append(r)

    metrics: Dict[str, Any] = {}
    anomalies: List[str] = []
    for metric, series in by_metric.items():
        series.sort(key=lambda x: x["date"])
        vals = [float(x["value"]) for x in series]
        unit = series[0].get("unit", "")
        half = len(vals) // 2 or 1
        earlier = statistics.mean(vals[:half])
        recent = statistics.mean(vals[half:])
        change = ((recent - earlier) / earlier * 100) if earlier else 0.0
        trend = "rising" if change > 15 else "falling" if change < -15 else "stable"
        anomaly = trend == "rising" and metric in ("vibration", "temperature")
        metrics[metric] = {"latest": round(vals[-1], 2), "unit": unit,
                           "earlier_avg": round(earlier, 2), "recent_avg": round(recent, 2),
                           "change_pct": round(change, 1), "trend": trend, "anomaly": anomaly}
        if anomaly:
            anomalies.append(
                f"{metric} {trend} {change:+.0f}% (recent avg {recent:.1f}{unit}, latest {vals[-1]:.1f}{unit})")

    return {"asset": asset_tag, "metrics": metrics, "anomalies": anomalies, "n_readings": len(rows)}


def readable(summary: Dict[str, Any]) -> str:
    if not summary["n_readings"]:
        return "(no sensor readings available)"
    lines = []
    for metric, d in summary["metrics"].items():
        flag = "  <-- ANOMALY" if d["anomaly"] else ""
        lines.append(
            f"{metric}: latest {d['latest']}{d['unit']}, trend {d['trend']} "
            f"({d['change_pct']:+}% recent vs earlier){flag}")
    return "\n".join(lines)
