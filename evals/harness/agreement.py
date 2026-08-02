"""Aggregate human feedback and simple inter-rater agreement."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any


def summarize_rubric_annotations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rubric_rows = [r for r in rows if r.get("kind") == "rubric"]
    by_criterion: dict[str, list[int]] = defaultdict(list)
    by_case: dict[str, list[dict[str, int]]] = defaultdict(list)

    for row in rubric_rows:
        scores = row.get("scores") or {}
        for key, value in scores.items():
            if isinstance(value, int):
                by_criterion[key].append(value)
        case_id = row.get("case_id") or row.get("id")
        if isinstance(scores, dict):
            by_case[str(case_id)].append(scores)

    criterion_means = {
        key: round(mean(values), 4) for key, values in sorted(by_criterion.items()) if values
    }
    return {
        "annotations": len(rubric_rows),
        "criterion_means": criterion_means,
        "cases_scored": len(by_case),
        "agreement": rubric_agreement(rubric_rows),
    }


def rubric_agreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Pair raters that scored the same case_id + response.

    Reports exact-match rate across criteria and mean absolute difference.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("kind") != "rubric":
            continue
        case_id = str(row.get("case_id") or "")
        response = str(row.get("response") or "")
        if not case_id:
            continue
        groups[(case_id, response)].append(row)

    exact_flags: list[bool] = []
    abs_diffs: list[float] = []
    paired_groups = 0

    for group in groups.values():
        if len(group) < 2:
            continue
        paired_groups += 1
        # Compare first two raters only (lab-scale).
        a = group[0].get("scores") or {}
        b = group[1].get("scores") or {}
        keys = sorted(set(a) | set(b))
        if not keys:
            continue
        matches = [a.get(k) == b.get(k) for k in keys]
        exact_flags.append(all(matches))
        diffs = []
        for key in keys:
            if key in a and key in b and isinstance(a[key], int) and isinstance(b[key], int):
                diffs.append(abs(a[key] - b[key]))
        if diffs:
            abs_diffs.append(mean(diffs))

    return {
        "paired_groups": paired_groups,
        "exact_match_rate": round(mean(exact_flags), 4) if exact_flags else None,
        "mean_abs_diff": round(mean(abs_diffs), 4) if abs_diffs else None,
    }


def summarize_pairwise_annotations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairwise = [r for r in rows if r.get("kind") == "pairwise"]
    wins = {"A": 0, "B": 0, "tie": 0}
    for row in pairwise:
        winner = row.get("winner")
        if winner in wins:
            wins[winner] += 1

    decisive = wins["A"] + wins["B"]
    return {
        "annotations": len(pairwise),
        "wins": wins,
        "win_rate_a": round(wins["A"] / decisive, 4) if decisive else None,
        "win_rate_b": round(wins["B"] / decisive, 4) if decisive else None,
        "agreement": pairwise_agreement(pairwise),
    }


def pairwise_agreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Agreement when ≥2 raters judged the same prompt + responses."""
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("prompt") or ""),
            str(row.get("response_a") or ""),
            str(row.get("response_b") or ""),
        )
        winner = row.get("winner")
        if winner in {"A", "B", "tie"}:
            groups[key].append(winner)

    paired = 0
    agree = 0
    for winners in groups.values():
        if len(winners) < 2:
            continue
        paired += 1
        if winners[0] == winners[1]:
            agree += 1

    return {
        "paired_groups": paired,
        "agreement_rate": round(agree / paired, 4) if paired else None,
    }


def summarize_feedback(
    rubric_rows: list[dict[str, Any]],
    pairwise_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "rubric": summarize_rubric_annotations(rubric_rows),
        "pairwise": summarize_pairwise_annotations(pairwise_rows),
    }
