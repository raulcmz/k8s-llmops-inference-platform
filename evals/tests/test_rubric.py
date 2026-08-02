import json
from pathlib import Path

import pytest

from evals.harness.rubric import default_rubric_path, load_rubric, validate_scores


def test_load_default_rubric():
    rubric = load_rubric(default_rubric_path())
    assert rubric.id == "response_quality_v1"
    assert set(rubric.criterion_ids) == {
        "instruction_following",
        "clarity",
        "concision",
        "safety_basic",
    }


def test_validate_scores_ok():
    rubric = load_rubric(default_rubric_path())
    scores = validate_scores(
        rubric,
        {
            "instruction_following": 2,
            "clarity": 4,
            "concision": 2,
            "safety_basic": 5,
        },
    )
    assert scores["instruction_following"] == 2


def test_validate_scores_rejects_out_of_range():
    rubric = load_rubric(default_rubric_path())
    with pytest.raises(ValueError, match="outside"):
        validate_scores(
            rubric,
            {
                "instruction_following": 0,
                "clarity": 4,
                "concision": 2,
                "safety_basic": 5,
            },
        )


def test_validate_scores_rejects_missing_key():
    rubric = load_rubric(default_rubric_path())
    with pytest.raises(ValueError, match="missing"):
        validate_scores(rubric, {"clarity": 3})


def test_rubric_json_is_valid_file():
    path = Path(__file__).resolve().parents[1] / "rubrics" / "response_quality_v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["id"] == "response_quality_v1"
