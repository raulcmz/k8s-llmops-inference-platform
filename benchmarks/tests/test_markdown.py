from benchmarks.harness.report import build_level_summary, render_concurrency_markdown
from benchmarks.harness.stream_client import StreamSample


def test_build_level_summary_throughput():
    samples = [
        StreamSample(
            case_id="c#1",
            model=None,
            prompt="p",
            ok=True,
            error=None,
            e2e_seconds=1.0,
            ttft_seconds=0.2,
            tpot_seconds=0.05,
            completion_tokens=4,
            prompt_tokens=2,
            chunks_with_text=3,
            response_preview="x",
        ),
        StreamSample(
            case_id="c#2",
            model=None,
            prompt="p",
            ok=True,
            error=None,
            e2e_seconds=1.0,
            ttft_seconds=0.3,
            tpot_seconds=0.06,
            completion_tokens=4,
            prompt_tokens=2,
            chunks_with_text=3,
            response_preview="y",
        ),
    ]
    summary = build_level_summary(samples, concurrency=2, wall_seconds=2.0)
    assert summary["concurrency"] == 2
    assert summary["requests_per_second"] == 1.0
    assert summary["ok"] == 2


def test_render_concurrency_markdown_has_table():
    report = {
        "created_at": "2026-08-03T00:00:00+00:00",
        "gateway_url": "http://127.0.0.1:8080",
        "suite": "smoke_latency",
        "case_id": "bench-short-es",
        "metadata": {"hardware": "cpu-lab"},
        "levels": [
            {
                "concurrency": 1,
                "summary": {
                    "concurrency": 1,
                    "requests": 3,
                    "ok": 3,
                    "failed": 0,
                    "wall_seconds": 9.0,
                    "requests_per_second": 0.3333,
                    "ttft_seconds": {"p50": 0.6, "p95": 1.2},
                    "tpot_seconds": {"p50": 0.13},
                    "e2e_seconds": {"p50": 3.0},
                },
            }
        ],
    }
    md = render_concurrency_markdown(report)
    assert "| concurrency | ok/total |" in md
    assert "cpu-lab" in md
    assert "| 1 | 3/3 |" in md
