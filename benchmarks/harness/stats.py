"""Latency statistics helpers (client-observed)."""

from __future__ import annotations

import math
from typing import Optional, Sequence


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    """
    Linear-interpolation percentile.

    pct in [0, 100]. Empty input → None.
    """
    if not values:
        return None
    if pct < 0 or pct > 100:
        raise ValueError("pct must be in [0, 100]")
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def summarize_latencies(values: Sequence[float]) -> dict[str, Optional[float]]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "p50": None,
            "p95": None,
        }
    total = float(sum(values))
    p50 = percentile(values, 50)
    p95 = percentile(values, 95)
    return {
        "count": len(values),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(total / len(values), 4),
        "p50": round(p50, 4) if p50 is not None else None,
        "p95": round(p95, 4) if p95 is not None else None,
    }
