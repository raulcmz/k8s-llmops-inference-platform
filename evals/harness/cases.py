"""Eval case schema and JSONL loader.

An eval case is one reproducible task: prompt (+ optional model) and
expectations used by automatic checks. Human rubrics come in a later task.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field


class Expectation(BaseModel):
    """Automatic expectations for a case (structural / heuristic checks)."""

    contains_any: list[str] = Field(default_factory=list)
    contains_all: list[str] = Field(default_factory=list)
    min_chars: Optional[int] = None
    max_chars: Optional[int] = None


class EvalCase(BaseModel):
    id: str
    prompt: str = Field(min_length=1)
    model: Optional[str] = None
    expect: Expectation = Field(default_factory=Expectation)


def load_cases_jsonl(path: Path) -> list[EvalCase]:
    """Load one EvalCase per non-empty JSONL line."""
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                payload = json.loads(line)
                cases.append(EvalCase.model_validate(payload))
            except Exception as exc:  # noqa: BLE001 - surface line context
                raise ValueError(f"{path}:{line_no}: invalid case: {exc}") from exc
    if not cases:
        raise ValueError(f"No cases found in {path}")
    return cases


def iter_case_files(cases_dir: Path) -> Iterator[Path]:
    yield from sorted(cases_dir.glob("*.jsonl"))
