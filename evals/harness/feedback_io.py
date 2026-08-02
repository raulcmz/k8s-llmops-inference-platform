"""Schemas and JSONL I/O for human feedback records."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class RubricAnnotation(BaseModel):
    id: str
    kind: Literal["rubric"] = "rubric"
    rubric_id: str
    case_id: Optional[str] = None
    source_report: Optional[str] = None
    prompt: str
    response: str
    rater_id: str
    scores: dict[str, int]
    notes: str = ""
    created_at: str = Field(default_factory=utc_now_iso)


class PairwiseAnnotation(BaseModel):
    id: str
    kind: Literal["pairwise"] = "pairwise"
    case_id: Optional[str] = None
    prompt: str
    response_a: str
    response_b: str
    order_presented: list[Literal["A", "B"]]
    winner: Literal["A", "B", "tie"]
    rater_id: str
    rationale: str = ""
    created_at: str = Field(default_factory=utc_now_iso)

    @field_validator("order_presented")
    @classmethod
    def check_order(cls, value: list[str]) -> list[str]:
        if sorted(value) != ["A", "B"]:
            raise ValueError("order_presented must be a permutation of ['A', 'B']")
        return value


FeedbackRecord = Union[RubricAnnotation, PairwiseAnnotation]


def append_jsonl(path: Path, record: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def load_feedback_dir(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl")):
        rows.extend(load_jsonl(path))
    return rows


def load_case_from_report(report_path: Path, case_id: str) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for row in report.get("results") or []:
        if row.get("id") == case_id:
            return {
                "case_id": case_id,
                "prompt": row.get("prompt") or "",
                "response": row.get("response") or "",
                "source_report": str(report_path),
                "passed": row.get("passed"),
            }
    raise ValueError(f"case_id {case_id!r} not found in {report_path}")
