from pathlib import Path

from evals.harness.cases import load_cases_jsonl


def test_load_smoke_suite():
    path = Path(__file__).resolve().parents[1] / "cases" / "smoke.jsonl"
    cases = load_cases_jsonl(path)
    assert len(cases) == 3
    assert cases[0].id == "smoke-greeting-es"
    assert cases[1].expect.contains_all
