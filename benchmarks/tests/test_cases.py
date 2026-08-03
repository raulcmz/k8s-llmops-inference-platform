from pathlib import Path

from benchmarks.harness.cases import load_cases_jsonl


def test_load_smoke_latency_suite():
    path = Path(__file__).resolve().parents[1] / "cases" / "smoke_latency.jsonl"
    cases = load_cases_jsonl(path)
    assert len(cases) == 3
    assert cases[0].id == "bench-short-es"
    assert cases[0].repeats == 1
