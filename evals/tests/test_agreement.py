from evals.harness.agreement import (
    pairwise_agreement,
    summarize_feedback,
    summarize_pairwise_annotations,
    summarize_rubric_annotations,
)
from evals.harness.feedback_io import load_jsonl
from pathlib import Path


def _example_rows():
    root = Path(__file__).resolve().parents[1] / "feedback" / "examples"
    rubric = load_jsonl(root / "rubric_sample.jsonl")
    pairwise = load_jsonl(root / "pairwise_sample.jsonl")
    return rubric, pairwise


def test_rubric_means_and_agreement_from_examples():
    rubric_rows, _ = _example_rows()
    summary = summarize_rubric_annotations(rubric_rows)
    assert summary["annotations"] == 2
    assert summary["criterion_means"]["clarity"] == 4
    assert summary["agreement"]["paired_groups"] == 1
    # instruction_following differs (1 vs 2) → not exact match
    assert summary["agreement"]["exact_match_rate"] == 0.0
    assert summary["agreement"]["mean_abs_diff"] == 0.25


def test_pairwise_win_rate():
    _, pairwise_rows = _example_rows()
    summary = summarize_pairwise_annotations(pairwise_rows)
    assert summary["wins"]["A"] == 1
    assert summary["win_rate_a"] == 1.0


def test_pairwise_agreement_two_raters():
    rows = [
        {
            "kind": "pairwise",
            "prompt": "p",
            "response_a": "a",
            "response_b": "b",
            "winner": "A",
        },
        {
            "kind": "pairwise",
            "prompt": "p",
            "response_a": "a",
            "response_b": "b",
            "winner": "A",
        },
    ]
    assert pairwise_agreement(rows)["agreement_rate"] == 1.0


def test_summarize_feedback_combines():
    rubric_rows, pairwise_rows = _example_rows()
    out = summarize_feedback(rubric_rows, pairwise_rows)
    assert out["rubric"]["annotations"] == 2
    assert out["pairwise"]["annotations"] == 1
