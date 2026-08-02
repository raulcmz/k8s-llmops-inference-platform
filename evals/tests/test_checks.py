from evals.harness.cases import Expectation
from evals.harness.checks import all_passed, extract_json_candidate, run_expectation_checks


def test_contains_any_and_all():
    expect = Expectation(
        contains_any=["Hola", "Hello"],
        contains_all=["Ana", "Madrid"],
    )
    text = "Hola, soy Ana de Madrid"
    results = run_expectation_checks(text, expect)
    assert all_passed(results)


def test_max_chars_fails():
    expect = Expectation(contains_any=["OK"], max_chars=2)
    results = run_expectation_checks("OK!!!", expect)
    by_name = {item.name: item for item in results}
    assert by_name["contains_any"].passed is True
    assert by_name["max_chars"].passed is False
    assert all_passed(results) is False


def test_json_equals_pass_raw():
    expect = Expectation(
        json_valid=True,
        json_object=True,
        json_required_keys=["name", "city"],
        json_equals={"name": "Ana", "city": "Madrid"},
    )
    results = run_expectation_checks('{"name": "Ana", "city": "Madrid"}', expect)
    assert all_passed(results)


def test_json_equals_pass_fenced():
    expect = Expectation(json_valid=True, json_equals={"name": "Ana", "city": "Madrid"})
    text = '```json\n{"name": "Ana", "city": "Madrid"}\n```'
    candidate, used_fence = extract_json_candidate(text)
    assert used_fence is True
    assert "Ana" in candidate
    results = run_expectation_checks(text, expect)
    assert all_passed(results)


def test_json_invalid_fails_downstream():
    expect = Expectation(
        json_valid=True,
        json_object=True,
        json_required_keys=["name"],
        json_equals={"name": "Ana"},
    )
    results = run_expectation_checks("not json at all", expect)
    by_name = {item.name: item for item in results}
    assert by_name["json_valid"].passed is False
    assert by_name["json_object"].passed is False
    assert by_name["json_required_keys"].passed is False
    assert by_name["json_equals"].passed is False
    assert all_passed(results) is False


def test_json_required_keys_and_equals_fail():
    expect = Expectation(
        json_valid=True,
        json_object=True,
        json_required_keys=["name", "city"],
        json_equals={"name": "Ana", "city": "Madrid"},
    )
    # Extra key → total equality fails; required keys still pass.
    results = run_expectation_checks(
        '{"name": "Ana", "city": "Madrid", "extra": 1}', expect
    )
    by_name = {item.name: item for item in results}
    assert by_name["json_required_keys"].passed is True
    assert by_name["json_equals"].passed is False
