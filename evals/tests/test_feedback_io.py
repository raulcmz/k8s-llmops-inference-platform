import json
from pathlib import Path

from evals.harness.feedback_io import (
    PairwiseAnnotation,
    RubricAnnotation,
    append_jsonl,
    load_case_from_report,
    load_jsonl,
    new_id,
)


def test_append_and_load_jsonl(tmp_path: Path):
    path = tmp_path / "a.jsonl"
    record = RubricAnnotation(
        id=new_id("ann"),
        rubric_id="response_quality_v1",
        case_id="c1",
        prompt="p",
        response="r",
        rater_id="raul",
        scores={"instruction_following": 3, "clarity": 3, "concision": 3, "safety_basic": 5},
    )
    append_jsonl(path, record)
    rows = load_jsonl(path)
    assert len(rows) == 1
    assert rows[0]["kind"] == "rubric"


def test_pairwise_order_validation():
    rec = PairwiseAnnotation(
        id="pw-1",
        prompt="p",
        response_a="a",
        response_b="b",
        order_presented=["B", "A"],
        winner="A",
        rater_id="raul",
    )
    assert rec.order_presented == ["B", "A"]


def test_load_case_from_report(tmp_path: Path):
    report = {
        "results": [
            {
                "id": "smoke-refusal-length",
                "prompt": "Di solo la palabra OK.",
                "response": "OK",
                "passed": True,
            }
        ]
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    loaded = load_case_from_report(path, "smoke-refusal-length")
    assert loaded["response"] == "OK"
