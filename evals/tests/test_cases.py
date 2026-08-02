from pathlib import Path

from evals.harness.cases import load_cases_jsonl


def test_load_smoke_suite():
    path = Path(__file__).resolve().parents[1] / "cases" / "smoke.jsonl"
    cases = load_cases_jsonl(path)
    assert len(cases) == 3
    assert cases[0].id == "smoke-greeting-es"
    json_case = cases[1]
    assert json_case.id == "smoke-json-keys"
    assert json_case.expect.json_valid is True
    assert json_case.expect.json_required_keys == ["name", "city"]
    assert json_case.expect.json_equals == {"name": "Ana", "city": "Madrid"}
