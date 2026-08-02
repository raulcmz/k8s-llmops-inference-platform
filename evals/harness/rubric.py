"""Load and validate human evaluation rubrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Scale(BaseModel):
    min: int = 1
    max: int = 5

    @model_validator(mode="after")
    def check_range(self) -> Scale:
        if self.min >= self.max:
            raise ValueError("scale.min must be < scale.max")
        return self


class Criterion(BaseModel):
    id: str
    name: str
    description: str = ""
    anchors: dict[str, str] = Field(default_factory=dict)


class Rubric(BaseModel):
    id: str
    version: int = 1
    description: str = ""
    scale: Scale = Field(default_factory=Scale)
    criteria: list[Criterion]

    @field_validator("criteria")
    @classmethod
    def non_empty_criteria(cls, value: list[Criterion]) -> list[Criterion]:
        if not value:
            raise ValueError("rubric must define at least one criterion")
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate criterion ids")
        return value

    @property
    def criterion_ids(self) -> list[str]:
        return [item.id for item in self.criteria]

    def criterion_map(self) -> dict[str, Criterion]:
        return {item.id: item for item in self.criteria}


def load_rubric(path: Path) -> Rubric:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Rubric.model_validate(payload)


def default_rubric_path() -> Path:
    return Path(__file__).resolve().parents[1] / "rubrics" / "response_quality_v1.json"


def validate_scores(rubric: Rubric, scores: dict[str, Any]) -> dict[str, int]:
    """
    Validate a scores map against the rubric.

    Requires every criterion id exactly once; values must be ints in scale.
    """
    expected = set(rubric.criterion_ids)
    got = set(scores.keys())
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    if missing or extra:
        raise ValueError(f"score keys mismatch missing={missing} extra={extra}")

    cleaned: dict[str, int] = {}
    for key, raw in scores.items():
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise ValueError(f"score for {key!r} must be int, got {type(raw).__name__}")
        if raw < rubric.scale.min or raw > rubric.scale.max:
            raise ValueError(
                f"score for {key!r}={raw} outside [{rubric.scale.min}, {rubric.scale.max}]"
            )
        cleaned[key] = raw
    return cleaned
