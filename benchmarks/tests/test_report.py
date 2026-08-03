from benchmarks.harness.report import build_summary, format_summary_line
from benchmarks.harness.stream_client import StreamSample


def _sample(**kwargs) -> StreamSample:
    base = dict(
        case_id="c",
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
    )
    base.update(kwargs)
    return StreamSample(**base)


def test_build_summary():
    summary = build_summary(
        [
            _sample(ttft_seconds=0.1, tpot_seconds=0.02, e2e_seconds=0.5),
            _sample(ttft_seconds=0.3, tpot_seconds=0.04, e2e_seconds=1.5),
            _sample(ok=False, ttft_seconds=None, tpot_seconds=None, e2e_seconds=None),
        ]
    )
    assert summary["requests"] == 3
    assert summary["ok"] == 2
    assert summary["failed"] == 1
    assert summary["ttft_seconds"]["p50"] == 0.2
    line = format_summary_line(summary)
    assert "ok=2/3" in line
