#!/usr/bin/env python3
"""CLI: baseline vs candidate promotion gate for gateway evals.

Example:
  python promote_gate.py \\
    --policy gates/smoke_promote_v1.json \\
    --baseline reports/smoke_baseline.json \\
    --candidate reports/smoke_candidate.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.harness.feedback_io import load_feedback_dir, load_jsonl
from evals.harness.gate import evaluate_gate, load_policy, load_report
from evals.harness.report import utc_now_iso, write_report

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_POLICY = EVALS_DIR / "gates" / "smoke_promote_v1.json"
DEFAULT_GATES_DIR = EVALS_DIR / "reports" / "gates"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote/block gate for eval reports")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--baseline", required=True, help="Baseline run_eval JSON report")
    parser.add_argument("--candidate", required=True, help="Candidate run_eval JSON report")
    parser.add_argument(
        "--human",
        action="store_true",
        help="Enable optional human rubric/pairwise rules",
    )
    parser.add_argument(
        "--rubric-dir",
        default=str(EVALS_DIR / "feedback" / "rubric"),
    )
    parser.add_argument(
        "--pairwise-dir",
        default=str(EVALS_DIR / "feedback" / "pairwise"),
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Also load feedback/examples/*.jsonl into human signals",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_GATES_DIR),
        help="Where to write the gate decision JSON",
    )
    return parser.parse_args()


def _load_human_rows(args: argparse.Namespace) -> tuple[list[dict], list[dict]]:
    rubric_rows = load_feedback_dir(Path(args.rubric_dir))
    pairwise_rows = load_feedback_dir(Path(args.pairwise_dir))
    if args.examples:
        examples = EVALS_DIR / "feedback" / "examples"
        if examples.is_dir():
            for path in sorted(examples.glob("*.jsonl")):
                for row in load_jsonl(path):
                    kind = row.get("kind")
                    if kind == "rubric":
                        rubric_rows.append(row)
                    elif kind == "pairwise":
                        pairwise_rows.append(row)
    return rubric_rows, pairwise_rows


def main() -> int:
    args = parse_args()
    policy_path = Path(args.policy)
    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)

    for path in (policy_path, baseline_path, candidate_path):
        if not path.is_file():
            print(f"missing file: {path}", file=sys.stderr)
            return 2

    policy = load_policy(policy_path)
    baseline = load_report(baseline_path)
    candidate = load_report(candidate_path)

    rubric_rows: list[dict] = []
    pairwise_rows: list[dict] = []
    if args.human or policy.human.enabled_by_default:
        rubric_rows, pairwise_rows = _load_human_rows(args)

    result = evaluate_gate(
        policy,
        baseline,
        candidate,
        human_enabled=args.human or policy.human.enabled_by_default,
        rubric_rows=rubric_rows,
        pairwise_rows=pairwise_rows,
    )

    result["created_at"] = utc_now_iso()
    result["baseline_path"] = str(baseline_path)
    result["candidate_path"] = str(candidate_path)
    result["policy_path"] = str(policy_path)
    result["human_enabled"] = bool(args.human or policy.human.enabled_by_default)

    stamp = utc_now_iso().replace(":", "").replace("+00:00", "Z")
    out_path = Path(args.reports_dir) / f"promote_{policy.id}_{stamp}.json"
    write_report(out_path, result)

    decision = result["decision"].upper()
    print(f"decision={decision} policy={policy.id}")
    for rule in result["rules"]:
        print(f"  [{rule['status'].upper()}] {rule['name']}: {rule['detail']}")
    print(f"report={out_path}")

    return 0 if result["decision"] == "promote" else 1


if __name__ == "__main__":
    raise SystemExit(main())
