import json
from pathlib import Path

from evals.harness.gate import evaluate_gate, load_policy


def _case(case_id: str, passed: bool, error: str | None = None) -> dict:
    return {
        "id": case_id,
        "passed": passed,
        "error": error,
        "checks": [],
    }


def _report(suite: str, cases: list[dict]) -> dict:
    total = len(cases)
    passed = sum(1 for c in cases if c.get("passed"))
    errors = sum(1 for c in cases if c.get("error"))
    return {
        "suite": suite,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "errors": errors,
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "failed_by_check": {},
        },
        "results": cases,
    }


def _policy() -> Path:
    return Path(__file__).resolve().parents[1] / "gates" / "smoke_promote_v1.json"


def test_load_smoke_policy():
    policy = load_policy(_policy())
    assert policy.id == "smoke_promote_v1"
    assert "smoke-json-keys" in policy.automatic.require_candidate_pass_case_ids


def test_promote_when_hard_cases_pass():
    policy = load_policy(_policy())
    baseline = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", True),
            _case("smoke-refusal-length", False),
        ],
    )
    candidate = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", True),
            _case("smoke-refusal-length", False),
        ],
    )
    out = evaluate_gate(policy, baseline, candidate)
    assert out["decision"] == "promote"
    assert not any(r["status"] == "fail" for r in out["rules"])


def test_block_when_json_hard_case_fails():
    policy = load_policy(_policy())
    baseline = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", True),
            _case("smoke-refusal-length", True),
        ],
    )
    candidate = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", False),
            _case("smoke-refusal-length", True),
        ],
    )
    out = evaluate_gate(policy, baseline, candidate)
    assert out["decision"] == "block"
    names = {r["name"]: r["status"] for r in out["rules"]}
    assert names["require_pass:smoke-json-keys"] == "fail"


def test_block_on_candidate_errors():
    policy = load_policy(_policy())
    baseline = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", True),
            _case("smoke-refusal-length", True),
        ],
    )
    # Hard cases still pass; transport error on soft case must block via errors.
    candidate = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", True),
            _case("smoke-refusal-length", False, error="gateway timeout"),
        ],
    )
    out = evaluate_gate(policy, baseline, candidate)
    assert out["decision"] == "block"
    err_rule = next(r for r in out["rules"] if r["name"] == "max_candidate_errors")
    assert err_rule["status"] == "fail"


def test_human_skip_without_data():
    policy = load_policy(_policy())
    baseline = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", True),
            _case("smoke-refusal-length", False),
        ],
    )
    candidate = baseline
    out = evaluate_gate(
        policy,
        baseline,
        candidate,
        human_enabled=True,
        rubric_rows=[],
        pairwise_rows=[],
    )
    human_rules = [r for r in out["rules"] if r["name"].startswith("human_")]
    assert human_rules
    assert all(r["status"] == "skip" for r in human_rules)
    assert out["decision"] == "promote"


def test_human_block_on_low_instruction_following():
    policy = load_policy(_policy())
    baseline = _report(
        "smoke",
        [
            _case("smoke-greeting-es", True),
            _case("smoke-json-keys", True),
            _case("smoke-refusal-length", True),
        ],
    )
    candidate = baseline
    rubric_rows = [
        {
            "kind": "rubric",
            "case_id": "smoke-refusal-length",
            "response": "x",
            "scores": {
                "instruction_following": 1,
                "clarity": 4,
                "concision": 2,
                "safety_basic": 5,
            },
        }
    ]
    out = evaluate_gate(
        policy,
        baseline,
        candidate,
        human_enabled=True,
        rubric_rows=rubric_rows,
        pairwise_rows=[],
    )
    assert out["decision"] == "block"
    rule = next(r for r in out["rules"] if r["name"] == "human_instruction_following_mean")
    assert rule["status"] == "fail"


def test_policy_file_is_json():
    raw = json.loads(_policy().read_text(encoding="utf-8"))
    assert raw["automatic"]["soft_case_ids"] == ["smoke-refusal-length"]
