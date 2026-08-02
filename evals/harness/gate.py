"""Promotion gate: compare baseline vs candidate eval reports under a policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from evals.harness.agreement import summarize_pairwise_annotations, summarize_rubric_annotations


class AutomaticPolicy(BaseModel):
    min_candidate_pass_rate: float = 0.0
    min_pass_rate_delta: float = -1.0
    max_candidate_errors: int = 0
    require_candidate_pass_case_ids: list[str] = Field(default_factory=list)
    soft_case_ids: list[str] = Field(default_factory=list)


class HumanPolicy(BaseModel):
    enabled_by_default: bool = False
    min_instruction_following_mean: float = 3.0
    min_pairwise_win_rate_vs_baseline: float = 0.5
    insufficient_data: Literal["skip", "block"] = "skip"


class GatePolicy(BaseModel):
    id: str
    version: int = 1
    suite: Optional[str] = None
    description: str = ""
    automatic: AutomaticPolicy = Field(default_factory=AutomaticPolicy)
    human: HumanPolicy = Field(default_factory=HumanPolicy)


class RuleResult(BaseModel):
    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str


def load_policy(path: Path) -> GatePolicy:
    return GatePolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("summary") or {}


def _results_by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in report.get("results") or []:
        case_id = row.get("id")
        if case_id:
            out[str(case_id)] = row
    return out


def evaluate_automatic(
    policy: GatePolicy,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> list[RuleResult]:
    rules: list[RuleResult] = []
    auto = policy.automatic
    base_sum = _summary(baseline)
    cand_sum = _summary(candidate)

    cand_errors = int(cand_sum.get("errors") or 0)
    cand_pass_rate = float(cand_sum.get("pass_rate") or 0.0)
    base_pass_rate = float(base_sum.get("pass_rate") or 0.0)
    delta = round(cand_pass_rate - base_pass_rate, 4)

    rules.append(
        RuleResult(
            name="max_candidate_errors",
            status="pass" if cand_errors <= auto.max_candidate_errors else "fail",
            detail=f"candidate_errors={cand_errors} max={auto.max_candidate_errors}",
        )
    )
    rules.append(
        RuleResult(
            name="min_candidate_pass_rate",
            status="pass" if cand_pass_rate + 1e-12 >= auto.min_candidate_pass_rate else "fail",
            detail=(
                f"candidate_pass_rate={cand_pass_rate} "
                f"min={auto.min_candidate_pass_rate}"
            ),
        )
    )
    rules.append(
        RuleResult(
            name="min_pass_rate_delta",
            status="pass" if delta + 1e-12 >= auto.min_pass_rate_delta else "fail",
            detail=(
                f"delta={delta} "
                f"(candidate={cand_pass_rate} baseline={base_pass_rate}) "
                f"min_delta={auto.min_pass_rate_delta}"
            ),
        )
    )

    cand_by_id = _results_by_id(candidate)
    for case_id in auto.require_candidate_pass_case_ids:
        row = cand_by_id.get(case_id)
        if row is None:
            rules.append(
                RuleResult(
                    name=f"require_pass:{case_id}",
                    status="fail",
                    detail="case missing from candidate report",
                )
            )
            continue
        passed = bool(row.get("passed"))
        rules.append(
            RuleResult(
                name=f"require_pass:{case_id}",
                status="pass" if passed else "fail",
                detail=f"passed={passed}",
            )
        )

    if auto.soft_case_ids:
        soft_bits = []
        for case_id in auto.soft_case_ids:
            row = cand_by_id.get(case_id)
            if row is None:
                soft_bits.append(f"{case_id}=missing")
            else:
                soft_bits.append(f"{case_id}=passed={bool(row.get('passed'))}")
        rules.append(
            RuleResult(
                name="soft_cases_observed",
                status="skip",
                detail=(
                    "soft cases do not block alone; "
                    + ", ".join(soft_bits)
                ),
            )
        )

    if policy.suite:
        base_suite = baseline.get("suite")
        cand_suite = candidate.get("suite")
        same = base_suite == cand_suite == policy.suite
        rules.append(
            RuleResult(
                name="suite_match",
                status="pass" if same else "fail",
                detail=(
                    f"policy_suite={policy.suite!r} "
                    f"baseline_suite={base_suite!r} "
                    f"candidate_suite={cand_suite!r}"
                ),
            )
        )

    return rules


def evaluate_human(
    policy: GatePolicy,
    *,
    rubric_rows: list[dict[str, Any]],
    pairwise_rows: list[dict[str, Any]],
) -> list[RuleResult]:
    """
    Optional human gates.

    - Rubric: mean of instruction_following across rubric annotations.
    - Pairwise: among decisive (non-tie) preferences, require win_rate_a >= threshold
      when annotations use response_a=candidate convention is NOT assumed.
      Lab convention for gate pairwise: winner labels refer to A=candidate, B=baseline
      when the annotation notes say so; we document and use win_rate of winner=='A'
      as candidate win rate when kind=pairwise rows are provided for the gate.
    """
    human = policy.human
    rules: list[RuleResult] = []
    mode = human.insufficient_data

    rubric_summary = summarize_rubric_annotations(rubric_rows)
    if_mean = (rubric_summary.get("criterion_means") or {}).get("instruction_following")
    if if_mean is None:
        rules.append(
            RuleResult(
                name="human_instruction_following_mean",
                status="skip" if mode == "skip" else "fail",
                detail="insufficient rubric data for instruction_following",
            )
        )
    else:
        rules.append(
            RuleResult(
                name="human_instruction_following_mean",
                status=(
                    "pass"
                    if float(if_mean) + 1e-12 >= human.min_instruction_following_mean
                    else "fail"
                ),
                detail=(
                    f"mean={if_mean} "
                    f"min={human.min_instruction_following_mean} "
                    f"n={rubric_summary.get('annotations')}"
                ),
            )
        )

    pairwise_summary = summarize_pairwise_annotations(pairwise_rows)
    win_rate_a = pairwise_summary.get("win_rate_a")
    if win_rate_a is None:
        rules.append(
            RuleResult(
                name="human_pairwise_win_rate_a",
                status="skip" if mode == "skip" else "fail",
                detail=(
                    "insufficient pairwise data "
                    "(lab convention: A=candidate, B=baseline)"
                ),
            )
        )
    else:
        rules.append(
            RuleResult(
                name="human_pairwise_win_rate_a",
                status=(
                    "pass"
                    if float(win_rate_a) + 1e-12 >= human.min_pairwise_win_rate_vs_baseline
                    else "fail"
                ),
                detail=(
                    f"win_rate_a={win_rate_a} "
                    f"min={human.min_pairwise_win_rate_vs_baseline} "
                    f"wins={pairwise_summary.get('wins')} "
                    "(A=candidate, B=baseline)"
                ),
            )
        )

    return rules


def decide(rules: list[RuleResult]) -> Literal["promote", "block"]:
    if any(rule.status == "fail" for rule in rules):
        return "block"
    return "promote"


def evaluate_gate(
    policy: GatePolicy,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    human_enabled: bool = False,
    rubric_rows: Optional[list[dict[str, Any]]] = None,
    pairwise_rows: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    rules = evaluate_automatic(policy, baseline, candidate)
    if human_enabled or policy.human.enabled_by_default:
        rules.extend(
            evaluate_human(
                policy,
                rubric_rows=rubric_rows or [],
                pairwise_rows=pairwise_rows or [],
            )
        )
    decision = decide(rules)
    return {
        "policy_id": policy.id,
        "decision": decision,
        "rules": [rule.model_dump() for rule in rules],
        "baseline_summary": _summary(baseline),
        "candidate_summary": _summary(candidate),
    }
