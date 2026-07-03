"""The readings adapter — recent operating conditions for an asset.

Real-time signals (vibration, temperature, pressure) enter through ONE small
interface, so RCA reasons over current plant state, not just paperwork. For the
demo a replayed CSV feeds it; in a real plant an OPC-UA / MQTT collector writes
to the same store (Postgres) and implements the same interface — designed in,
not bolted on.
"""
from __future__ import annotations

import csv
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol


@dataclass
class ReadingPoint:
    ts: datetime.date
    value: float
    unit: str = ""


@dataclass
class TrendAnalysis:
    parameter: str
    count: int
    first: float
    last: float
    mean: float
    peak: float
    pct_change: float          # last vs first, %
    rising: bool
    unit: str = ""

    def describe(self) -> str:
        arrow = "rising" if self.rising else "stable/falling"
        return (f"{self.parameter} {arrow}: {self.first:g} -> {self.last:g}{self.unit} "
                f"({self.pct_change:+.0f}%, peak {self.peak:g}{self.unit}, n={self.count})")


class ReadingsSource(Protocol):
    def series(self, asset: str, parameter: str,
               since: Optional[datetime.date] = None) -> List[ReadingPoint]: ...
    def parameters(self, asset: str) -> List[str]: ...


class FileReadingsSource:
    """Replay readings from a CSV: asset_tag,parameter,timestamp,value,unit."""

    def __init__(self, path):
        self._by_asset: Dict[str, Dict[str, List[ReadingPoint]]] = {}
        p = Path(path)
        if not p.exists():
            return
        with p.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    ts = datetime.date.fromisoformat(row["timestamp"].strip()[:10])
                    val = float(row["value"])
                except (KeyError, ValueError):
                    continue
                a = self._by_asset.setdefault(row["asset_tag"], {})
                a.setdefault(row["parameter"], []).append(
                    ReadingPoint(ts, val, row.get("unit", "")))
        for params in self._by_asset.values():
            for pts in params.values():
                pts.sort(key=lambda r: r.ts)

    def parameters(self, asset: str) -> List[str]:
        return sorted(self._by_asset.get(asset, {}))

    def series(self, asset: str, parameter: str,
               since: Optional[datetime.date] = None) -> List[ReadingPoint]:
        pts = self._by_asset.get(asset, {}).get(parameter, [])
        return [p for p in pts if since is None or p.ts >= since]


def analyze(points: List[ReadingPoint], parameter: str,
            rise_threshold_pct: float = 25.0) -> Optional[TrendAnalysis]:
    """Deterministic trend summary — no AI. 'rising' if the end is meaningfully
    above the start."""
    if not points:
        return None
    values = [p.value for p in points]
    first, last = values[0], values[-1]
    pct = ((last - first) / first * 100.0) if first else 0.0
    return TrendAnalysis(
        parameter=parameter, count=len(values), first=first, last=last,
        mean=round(sum(values) / len(values), 3), peak=max(values),
        pct_change=round(pct, 1), rising=pct >= rise_threshold_pct,
        unit=points[-1].unit,
    )
