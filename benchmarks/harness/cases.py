"""Benchmark case schema and JSONL loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class BenchCase(BaseModel):
    id: str
    prompt: str = Field(min_length=1)
    model: Optional[str] = None
    repeats: int = Field(default=1, ge=1, le=100)


def load_cases_jsonl(path: Path) -> list[BenchCase]:
    cases: list[BenchCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                cases.append(BenchCase.model_validate(json.loads(line)))
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"{path}:{line_no}: invalid case: {exc}") from exc
    if not cases:
        raise ValueError(f"No cases found in {path}")
    return cases
