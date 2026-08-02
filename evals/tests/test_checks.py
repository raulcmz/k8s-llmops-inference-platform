from evals.harness.cases import Expectation
from evals.harness.checks import all_passed, run_expectation_checks


def test_contains_any_and_all():
    expect = Expectation(
        contains_any=["Hola", "Hello"],
        contains_all=["Ana", "Madrid"],
    )
    text = 'Hola, soy Ana de Madrid'
    results = run_expectation_checks(text, expect)
    assert all_passed(results)


def test_max_chars_fails():
    expect = Expectation(contains_any=["OK"], max_chars=2)
    results = run_expectation_checks("OK!!!", expect)
    by_name = {item.name: item for item in results}
    assert by_name["contains_any"].passed is True
    assert by_name["max_chars"].passed is False
    assert all_passed(results) is False
