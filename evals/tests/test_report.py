from evals.harness.report import format_check_lines, summarize


def test_summarize_failed_by_check():
    results = [
        {
            "passed": True,
            "checks": [{"name": "contains_any", "passed": True}],
            "error": None,
        },
        {
            "passed": False,
            "checks": [
                {"name": "json_valid", "passed": False, "detail": "parse_error"},
                {"name": "json_equals", "passed": False, "detail": "skipped"},
            ],
            "error": None,
        },
        {
            "passed": False,
            "checks": [{"name": "json_valid", "passed": False, "detail": "x"}],
            "error": None,
        },
    ]
    summary = summarize(results)
    assert summary["total"] == 3
    assert summary["passed"] == 1
    assert summary["failed"] == 2
    assert summary["failed_by_check"] == {"json_equals": 1, "json_valid": 2}


def test_format_check_lines():
    lines = format_check_lines(
        [
            {"name": "json_valid", "passed": True, "detail": "ok (raw)"},
            {"name": "json_equals", "passed": False, "detail": "got={} want={}"},
        ]
    )
    assert lines[0].startswith("    - json_valid: ok")
    assert "FAIL" in lines[1]
