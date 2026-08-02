"""Build and write eval run reports."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.get("passed"))
    errors = sum(1 for item in results if item.get("error"))

    failed_by_check: Counter[str] = Counter()
    for item in results:
        if item.get("passed"):
            continue
        for check in item.get("checks") or []:
            if not check.get("passed"):
                failed_by_check[check.get("name") or "unknown"] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "errors": errors,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "failed_by_check": dict(sorted(failed_by_check.items())),
    }


def format_check_lines(checks: list[dict[str, Any]]) -> list[str]:
    """Human-readable check lines for console output."""
    lines: list[str] = []
    for check in checks:
        status = "ok" if check.get("passed") else "FAIL"
        name = check.get("name", "?")
        detail = check.get("detail", "")
        lines.append(f"    - {name}: {status} ({detail})")
    return lines
