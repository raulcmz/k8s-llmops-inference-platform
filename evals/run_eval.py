#!/usr/bin/env python3
"""CLI: run automatic eval cases against the LLM gateway.

Example:
  export GATEWAY_URL=http://127.0.0.1:8080
  python run_eval.py --suite smoke
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python run_eval.py` from the evals/ directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.harness.cases import load_cases_jsonl
from evals.harness.checks import all_passed, run_expectation_checks
from evals.harness.gateway import GatewayError, call_chat
from evals.harness.report import summarize, utc_now_iso, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run gateway eval suites")
    parser.add_argument(
        "--suite",
        default="smoke",
        help="Suite file name without extension under evals/cases/ (default: smoke)",
    )
    parser.add_argument(
        "--gateway-url",
        default=None,
        help="Gateway base URL (default: env GATEWAY_URL or http://127.0.0.1:8080)",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(Path(__file__).resolve().parent / "reports"),
        help="Directory for JSON reports",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-request timeout when calling /chat",
    )
    return parser.parse_args()


def resolve_gateway_url(cli_value: str | None) -> str:
    import os

    return (cli_value or os.getenv("GATEWAY_URL") or "http://127.0.0.1:8080").rstrip(
        "/"
    )


def main() -> int:
    args = parse_args()
    gateway_url = resolve_gateway_url(args.gateway_url)
    cases_path = Path(__file__).resolve().parent / "cases" / f"{args.suite}.jsonl"
    if not cases_path.is_file():
        print(f"Suite not found: {cases_path}", file=sys.stderr)
        return 2

    cases = load_cases_jsonl(cases_path)
    results = []

    print(f"gateway={gateway_url}")
    print(f"suite={cases_path.name} cases={len(cases)}")

    for case in cases:
        row: dict = {
            "id": case.id,
            "prompt": case.prompt,
            "model": case.model,
            "passed": False,
            "checks": [],
            "error": None,
            "response": None,
            "latency_ms": None,
            "backend": None,
        }
        try:
            body = call_chat(
                base_url=gateway_url,
                prompt=case.prompt,
                model=case.model,
                timeout_seconds=args.timeout_seconds,
            )
            text = body.get("response") or ""
            checks = run_expectation_checks(text, case.expect)
            row["response"] = text
            row["latency_ms"] = body.get("latency_ms")
            row["backend"] = body.get("backend")
            row["checks"] = [check.__dict__ for check in checks]
            row["passed"] = all_passed(checks)
        except GatewayError as exc:
            row["error"] = str(exc)
            row["passed"] = False

        status = "PASS" if row["passed"] else "FAIL"
        print(f"[{status}] {case.id}")
        results.append(row)

    summary = summarize(results)
    report = {
        "created_at": utc_now_iso(),
        "gateway_url": gateway_url,
        "suite": args.suite,
        "summary": summary,
        "results": results,
    }

    stamp = utc_now_iso().replace(":", "").replace("+00:00", "Z")
    report_path = Path(args.reports_dir) / f"{args.suite}_{stamp}.json"
    write_report(report_path, report)

    print(
        "summary "
        f"passed={summary['passed']}/{summary['total']} "
        f"pass_rate={summary['pass_rate']} "
        f"report={report_path}"
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
