from benchmarks.harness.concurrency import parse_concurrency_list, run_concurrency_level
from benchmarks.harness.stream_client import StreamSample


def test_parse_concurrency_list():
    assert parse_concurrency_list("1,2,4") == [1, 2, 4]
    assert parse_concurrency_list(" 3 ") == [3]


def test_run_concurrency_level_uses_pool(monkeypatch):
    calls: list[int] = []

    def fake_run_stream_sample(**kwargs):
        calls.append(1)
        return StreamSample(
            case_id=kwargs["case_id"],
            model=kwargs.get("model"),
            prompt=kwargs["prompt"],
            ok=True,
            error=None,
            e2e_seconds=0.5,
            ttft_seconds=0.1,
            tpot_seconds=0.05,
            completion_tokens=3,
            prompt_tokens=2,
            chunks_with_text=2,
            response_preview="ok",
        )

    monkeypatch.setattr(
        "benchmarks.harness.concurrency.run_stream_sample",
        fake_run_stream_sample,
    )

    samples, wall = run_concurrency_level(
        base_url="http://example",
        case_id="bench-short-es",
        prompt="hola",
        model=None,
        concurrency=2,
        requests_per_level=4,
        timeout_seconds=10,
    )
    assert len(samples) == 4
    assert len(calls) == 4
    assert wall >= 0
    assert all(sample.ok for sample in samples)
