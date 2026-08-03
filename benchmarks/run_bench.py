#!/usr/bin/env python3
"""CLI: measure how fast the gateway answers (serving benchmark).

Two modes:

1) Simple suite (one request after another) — good first check:
     python run_bench.py --suite smoke_latency

2) Concurrency sweep (several chats at once) — shows queueing under load:
     python run_bench.py --suite smoke_latency --case-id bench-short-es \\
       --concurrency 1,2,4 --requests-per-level 3 --write-markdown
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.harness.cases import BenchCase, load_cases_jsonl
from benchmarks.harness.concurrency import parse_concurrency_list, run_concurrency_level
from benchmarks.harness.report import (
    build_level_summary,
    build_summary,
    format_summary_line,
    sample_to_dict,
    utc_now_iso,
    write_markdown,
    write_report,
)
from benchmarks.harness.stream_client import BenchClientError, StreamSample, run_stream_sample

BENCH_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark gateway /chat/stream latency. "
            "Use --concurrency for parallel load; omit it for a simple sequential suite."
        )
    )
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
        help='JSON notes, e.g. \'{"hardware":"cpu-lab","backend":"ollama","model":"mistral:7b"}\'',
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Required with --concurrency: which single prompt/case to repeat under load",
    )
    parser.add_argument(
        "--concurrency",
        default=None,
        help="Comma list of parallel chat counts, e.g. 1,2,4 (enables sweep mode)",
    )
    parser.add_argument(
        "--requests-per-level",
        type=int,
        default=3,
        help="How many total requests to send at each concurrency level (default: 3)",
    )
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="Also write a .md table next to the JSON report (concurrency mode)",
    )
    return parser.parse_args()


def resolve_gateway_url(cli_value: str | None) -> str:
    return (cli_value or os.getenv("GATEWAY_URL") or "http://127.0.0.1:8080").rstrip("/")


def _failed_sample(case: BenchCase, label: str, error: str) -> StreamSample:
    return StreamSample(
        case_id=label,
        model=case.model,
        prompt=case.prompt,
        ok=False,
        error=error,
        e2e_seconds=None,
        ttft_seconds=None,
        tpot_seconds=None,
        completion_tokens=None,
        prompt_tokens=None,
        chunks_with_text=0,
        response_preview="",
    )


def run_sequential(args: argparse.Namespace, gateway_url: str, cases: list[BenchCase]) -> int:
    samples: list[StreamSample] = []
    print(f"gateway={gateway_url}")
    print(f"mode=sequential suite={args.suite} cases={len(cases)}")

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
                sample = _failed_sample(case, label, str(exc))
            status = "OK" if sample.ok else "FAIL"
            print(
                f"[{status}] {sample.case_id} "
                f"ttft={sample.ttft_seconds}s "
                f"tpot={sample.tpot_seconds}s "
                f"e2e={sample.e2e_seconds}s"
            )
            samples.append(sample)

    metadata = json.loads(args.metadata) if args.metadata else {}
    summary = build_summary(samples)
    report = {
        "created_at": utc_now_iso(),
        "kind": "serving_benchmark",
        "mode": "sequential",
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


def run_concurrency_sweep(
    args: argparse.Namespace,
    gateway_url: str,
    cases: list[BenchCase],
) -> int:
    if not args.case_id:
        print("--case-id is required with --concurrency", file=sys.stderr)
        return 2

    selected = next((case for case in cases if case.id == args.case_id), None)
    if selected is None:
        known = ", ".join(case.id for case in cases)
        print(f"unknown case-id {args.case_id!r}; known: {known}", file=sys.stderr)
        return 2

    levels_n = parse_concurrency_list(args.concurrency)
    metadata = json.loads(args.metadata) if args.metadata else {}

    print(f"gateway={gateway_url}")
    print(
        f"mode=concurrency_sweep suite={args.suite} case_id={selected.id} "
        f"levels={levels_n} requests_per_level={args.requests_per_level}"
    )

    levels_out = []
    any_fail = False

    for concurrency in levels_n:
        print(f"--- concurrency={concurrency} ---")
        samples, wall = run_concurrency_level(
            base_url=gateway_url,
            case_id=selected.id,
            prompt=selected.prompt,
            model=selected.model,
            concurrency=concurrency,
            requests_per_level=args.requests_per_level,
            timeout_seconds=args.timeout_seconds,
        )
        summary = build_level_summary(samples, concurrency=concurrency, wall_seconds=wall)
        for sample in samples:
            status = "OK" if sample.ok else "FAIL"
            print(
                f"[{status}] {sample.case_id} "
                f"ttft={sample.ttft_seconds}s "
                f"tpot={sample.tpot_seconds}s "
                f"e2e={sample.e2e_seconds}s"
            )
        print("level " + format_summary_line(summary))
        if summary["failed"]:
            any_fail = True
        levels_out.append(
            {
                "concurrency": concurrency,
                "summary": summary,
                "samples": [sample_to_dict(s) for s in samples],
            }
        )

    report = {
        "created_at": utc_now_iso(),
        "kind": "serving_benchmark",
        "mode": "concurrency_sweep",
        "gateway_url": gateway_url,
        "suite": args.suite,
        "case_id": selected.id,
        "metadata": metadata,
        "levels": levels_out,
    }

    stamp = utc_now_iso().replace(":", "").replace("+00:00", "Z")
    stem = f"{args.suite}_conc_{selected.id}_{stamp}"
    report_path = Path(args.reports_dir) / f"{stem}.json"
    write_report(report_path, report)
    print(f"report={report_path}")

    if args.write_markdown:
        md_path = Path(args.reports_dir) / f"{stem}.md"
        write_markdown(md_path, report)
        print(f"markdown={md_path}")

    return 1 if any_fail else 0


def main() -> int:
    args = parse_args()
    gateway_url = resolve_gateway_url(args.gateway_url)
    cases_path = BENCH_DIR / "cases" / f"{args.suite}.jsonl"
    if not cases_path.is_file():
        print(f"Suite not found: {cases_path}", file=sys.stderr)
        return 2

    cases = load_cases_jsonl(cases_path)

    if args.concurrency:
        return run_concurrency_sweep(args, gateway_url, cases)
    if args.write_markdown:
        print("--write-markdown requires --concurrency (table is for sweeps)", file=sys.stderr)
        return 2
    return run_sequential(args, gateway_url, cases)


if __name__ == "__main__":
    raise SystemExit(main())
