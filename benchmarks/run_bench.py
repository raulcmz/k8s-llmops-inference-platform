#!/usr/bin/env python3
"""CLI: run serving latency benchmarks against the gateway /chat/stream.

Example:
  export GATEWAY_URL=http://127.0.0.1:8080
  python run_bench.py --suite smoke_latency
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.harness.cases import load_cases_jsonl
from benchmarks.harness.report import (
    build_summary,
    format_summary_line,
    sample_to_dict,
    utc_now_iso,
    write_report,
)
from benchmarks.harness.stream_client import BenchClientError, run_stream_sample

BENCH_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run gateway serving benchmarks")
    parser.add_argument(
        "--suite",
        default="smoke_latency",
        help="Suite file under benchmarks/cases/ without extension",
    )
    parser.add_argument("--gateway-url", default=None)
    parser.add_argument(
        "--reports-dir",
        default=str(BENCH_DIR / "reports"),
    )
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--metadata",
        default=None,
        help="Optional JSON object string stored in the report (hardware notes, etc.)",
    )
    return parser.parse_args()


def resolve_gateway_url(cli_value: str | None) -> str:
    return (cli_value or os.getenv("GATEWAY_URL") or "http://127.0.0.1:8080").rstrip("/")


def main() -> int:
    import json

    args = parse_args()
    gateway_url = resolve_gateway_url(args.gateway_url)
    cases_path = BENCH_DIR / "cases" / f"{args.suite}.jsonl"
    if not cases_path.is_file():
        print(f"Suite not found: {cases_path}", file=sys.stderr)
        return 2

    metadata = {}
    if args.metadata:
        metadata = json.loads(args.metadata)

    cases = load_cases_jsonl(cases_path)
    samples = []

    print(f"gateway={gateway_url}")
    print(f"suite={cases_path.name} cases={len(cases)}")

    for case in cases:
        for repeat_idx in range(case.repeats):
            label = case.id if case.repeats == 1 else f"{case.id}#{repeat_idx + 1}"
            try:
                sample = run_stream_sample(
                    base_url=gateway_url,
                    case_id=label,
                    prompt=case.prompt,
                    model=case.model,
                    timeout_seconds=args.timeout_seconds,
                )
            except BenchClientError as exc:
                print(f"[FAIL] {label} error={exc}")
                from benchmarks.harness.stream_client import StreamSample

                sample = StreamSample(
                    case_id=label,
                    model=case.model,
                    prompt=case.prompt,
                    ok=False,
                    error=str(exc),
                    e2e_seconds=None,
                    ttft_seconds=None,
                    tpot_seconds=None,
                    completion_tokens=None,
                    prompt_tokens=None,
                    chunks_with_text=0,
                    response_preview="",
                )
            status = "OK" if sample.ok else "FAIL"
            print(
                f"[{status}] {sample.case_id} "
                f"ttft={sample.ttft_seconds}s "
                f"tpot={sample.tpot_seconds}s "
                f"e2e={sample.e2e_seconds}s"
            )
            samples.append(sample)

    summary = build_summary(samples)
    report = {
        "created_at": utc_now_iso(),
        "kind": "serving_benchmark",
        "gateway_url": gateway_url,
        "suite": args.suite,
        "metadata": metadata,
        "summary": summary,
        "samples": [sample_to_dict(s) for s in samples],
    }

    stamp = utc_now_iso().replace(":", "").replace("+00:00", "Z")
    report_path = Path(args.reports_dir) / f"{args.suite}_{stamp}.json"
    write_report(report_path, report)

    print("summary " + format_summary_line(summary) + f" report={report_path}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
