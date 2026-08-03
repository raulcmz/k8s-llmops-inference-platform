"""Benchmark report helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.harness.stats import summarize_latencies
from benchmarks.harness.stream_client import StreamSample


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_summary(samples: list[StreamSample]) -> dict[str, Any]:
    ok_samples = [s for s in samples if s.ok]
    return {
        "requests": len(samples),
        "ok": len(ok_samples),
        "failed": len(samples) - len(ok_samples),
        "ttft_seconds": summarize_latencies(
            [s.ttft_seconds for s in ok_samples if s.ttft_seconds is not None]
        ),
        "tpot_seconds": summarize_latencies(
            [s.tpot_seconds for s in ok_samples if s.tpot_seconds is not None]
        ),
        "e2e_seconds": summarize_latencies(
            [s.e2e_seconds for s in ok_samples if s.e2e_seconds is not None]
        ),
    }


def sample_to_dict(sample: StreamSample) -> dict[str, Any]:
    return {
        "case_id": sample.case_id,
        "model": sample.model,
        "prompt": sample.prompt,
        "ok": sample.ok,
        "error": sample.error,
        "e2e_seconds": sample.e2e_seconds,
        "ttft_seconds": sample.ttft_seconds,
        "tpot_seconds": sample.tpot_seconds,
        "completion_tokens": sample.completion_tokens,
        "prompt_tokens": sample.prompt_tokens,
        "chunks_with_text": sample.chunks_with_text,
        "response_preview": sample.response_preview,
    }


def format_summary_line(summary: dict[str, Any]) -> str:
    ttft = summary.get("ttft_seconds") or {}
    tpot = summary.get("tpot_seconds") or {}
    e2e = summary.get("e2e_seconds") or {}
    return (
        f"ok={summary.get('ok')}/{summary.get('requests')} "
        f"ttft_p50={ttft.get('p50')} ttft_p95={ttft.get('p95')} "
        f"tpot_p50={tpot.get('p50')} e2e_p50={e2e.get('p50')}"
    )
