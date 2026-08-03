from benchmarks.harness.stats import percentile, summarize_latencies


def test_percentile_p50_odd():
    assert percentile([1.0, 2.0, 3.0], 50) == 2.0


def test_percentile_empty():
    assert percentile([], 50) is None


def test_summarize_latencies():
    summary = summarize_latencies([1.0, 2.0, 3.0, 4.0])
    assert summary["count"] == 4
    assert summary["min"] == 1.0
    assert summary["max"] == 4.0
    # Linear interpolation: p50 midway between 2 and 3
    assert summary["p50"] == 2.5
    assert summary["p95"] == 3.85
