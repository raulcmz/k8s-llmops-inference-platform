"""Benchmark report helpers (JSON + simple Markdown tables)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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


def build_level_summary(
    samples: list[StreamSample],
    *,
    concurrency: int,
    wall_seconds: float,
) -> dict[str, Any]:
    """Summary for one concurrency level, including throughput."""
    summary = build_summary(samples)
    ok = int(summary["ok"])
    wall = round(wall_seconds, 4)
    req_per_sec = round(ok / wall_seconds, 4) if wall_seconds > 0 else None
    summary.update(
        {
            "concurrency": concurrency,
            "wall_seconds": wall,
            "requests_per_second": req_per_sec,
        }
    )
    return summary


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
    extra = ""
    if "concurrency" in summary:
        extra = (
            f" concurrency={summary.get('concurrency')} "
            f"wall={summary.get('wall_seconds')}s "
            f"req_per_s={summary.get('requests_per_second')}"
        )
    return (
        f"ok={summary.get('ok')}/{summary.get('requests')} "
        f"ttft_p50={ttft.get('p50')} ttft_p95={ttft.get('p95')} "
        f"tpot_p50={tpot.get('p50')} e2e_p50={e2e.get('p50')}"
        f"{extra}"
    )


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.4f}"


def render_concurrency_markdown(report: dict[str, Any]) -> str:
    """
    Build a Markdown table a human can paste into notes.

    Columns are explained in benchmarks/README.md (beginner section).
    """
    metadata = report.get("metadata") or {}
    lines = [
        "# Serving benchmark (concurrency sweep)",
        "",
        f"- created_at: `{report.get('created_at')}`",
        f"- gateway: `{report.get('gateway_url')}`",
        f"- suite: `{report.get('suite')}`",
        f"- case_id: `{report.get('case_id')}`",
        f"- metadata: `{json.dumps(metadata, ensure_ascii=False)}`",
        "",
        "How to read the table:",
        "",
        "- **concurrency**: how many chats we kept open at the same time",
        "- **ok/total**: how many requests finished without error",
        "- **ttft_p50 / ttft_p95**: typical vs \"slow tail\" wait until the first word",
        "- **tpot_p50**: typical time per output token after the first",
        "- **e2e_p50**: typical full-answer time for one request",
        "- **wall_s**: clock time to finish the whole batch at that level",
        "- **req/s**: successful requests finished per second (batch throughput)",
        "",
        "| concurrency | ok/total | ttft_p50 | ttft_p95 | tpot_p50 | e2e_p50 | wall_s | req/s |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for level in report.get("levels") or []:
        summary = level.get("summary") or {}
        ttft = summary.get("ttft_seconds") or {}
        tpot = summary.get("tpot_seconds") or {}
        e2e = summary.get("e2e_seconds") or {}
        ok = summary.get("ok")
        total = summary.get("requests")
        lines.append(
            "| {c} | {ok}/{total} | {ttft50} | {ttft95} | {tpot50} | {e2e50} | {wall} | {rps} |".format(
                c=summary.get("concurrency"),
                ok=ok,
                total=total,
                ttft50=_fmt(ttft.get("p50")),
                ttft95=_fmt(ttft.get("p95")),
                tpot50=_fmt(tpot.get("p50")),
                e2e50=_fmt(e2e.get("p50")),
                wall=_fmt(summary.get("wall_seconds")),
                rps=_fmt(summary.get("requests_per_second")),
            )
        )

    lines.append("")
    lines.append(
        "_Numbers are only meaningful with the metadata above "
        "(CPU vs GPU, Ollama vs vLLM, model name)._"
    )
    lines.append("")
    return "\n".join(lines)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_concurrency_markdown(report), encoding="utf-8")
