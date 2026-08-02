"""Build and write eval run reports."""

from __future__ import annotations

import json
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
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "errors": errors,
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }
