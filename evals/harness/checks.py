"""Automatic checks against model output (no LLM-as-judge yet)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from evals.harness.cases import Expectation

_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class ParsedJson:
    """Result of attempting to parse model text as JSON."""

    value: Any
    candidate: str
    used_fence: bool
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def extract_json_candidate(text: str) -> tuple[str, bool]:
    """
    Pick a JSON candidate from raw model text.

    Prefer a fenced ```json ... ``` / ``` ... ``` block when present;
    otherwise use the stripped full text. Returns (candidate, used_fence).
    """
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip(), True
    return text.strip(), False


def parse_json_text(text: str) -> ParsedJson:
    candidate, used_fence = extract_json_candidate(text)
    try:
        return ParsedJson(
            value=json.loads(candidate),
            candidate=candidate,
            used_fence=used_fence,
        )
    except json.JSONDecodeError as exc:
        return ParsedJson(
            value=None,
            candidate=candidate,
            used_fence=used_fence,
            error=f"{exc.msg} (line {exc.lineno} col {exc.colno})",
        )


def _wants_json_checks(expect: Expectation) -> bool:
    return (
        expect.json_valid is not None
        or expect.json_object is not None
        or bool(expect.json_required_keys)
        or expect.json_equals is not None
    )


def run_expectation_checks(text: str, expect: Expectation) -> list[CheckResult]:
    results: list[CheckResult] = []

    if expect.contains_any:
        hit = next((token for token in expect.contains_any if token in text), None)
        results.append(
            CheckResult(
                name="contains_any",
                passed=hit is not None,
                detail=f"matched={hit!r}" if hit else f"none of {expect.contains_any!r}",
            )
        )

    if expect.contains_all:
        missing = [token for token in expect.contains_all if token not in text]
        results.append(
            CheckResult(
                name="contains_all",
                passed=not missing,
                detail="ok" if not missing else f"missing={missing!r}",
            )
        )

    if expect.min_chars is not None:
        ok = len(text) >= expect.min_chars
        results.append(
            CheckResult(
                name="min_chars",
                passed=ok,
                detail=f"len={len(text)} min={expect.min_chars}",
            )
        )

    if expect.max_chars is not None:
        ok = len(text) <= expect.max_chars
        results.append(
            CheckResult(
                name="max_chars",
                passed=ok,
                detail=f"len={len(text)} max={expect.max_chars}",
            )
        )

    if _wants_json_checks(expect):
        parsed = parse_json_text(text)
        fence_note = "fence" if parsed.used_fence else "raw"

        if expect.json_valid is not None:
            # json_valid:true means we require a successful parse.
            # json_valid:false means we require parse failure (negative case).
            want_valid = expect.json_valid
            is_valid = parsed.ok
            passed = is_valid is want_valid
            if want_valid:
                detail = (
                    f"ok ({fence_note})"
                    if is_valid
                    else f"parse_error={parsed.error!r} ({fence_note})"
                )
            else:
                detail = (
                    f"expected_invalid got_valid ({fence_note})"
                    if is_valid
                    else f"invalid_as_expected ({fence_note})"
                )
            results.append(
                CheckResult(name="json_valid", passed=passed, detail=detail)
            )

        # Downstream structural checks only make sense on a successful parse.
        if not parsed.ok:
            skip_detail = f"skipped: not_json ({parsed.error}) ({fence_note})"
            if expect.json_object is not None:
                results.append(
                    CheckResult(name="json_object", passed=False, detail=skip_detail)
                )
            if expect.json_required_keys:
                results.append(
                    CheckResult(
                        name="json_required_keys",
                        passed=False,
                        detail=skip_detail,
                    )
                )
            if expect.json_equals is not None:
                results.append(
                    CheckResult(name="json_equals", passed=False, detail=skip_detail)
                )
        else:
            if expect.json_object is not None:
                is_obj = isinstance(parsed.value, dict)
                want_obj = expect.json_object
                passed = is_obj is want_obj
                results.append(
                    CheckResult(
                        name="json_object",
                        passed=passed,
                        detail=(
                            f"type={type(parsed.value).__name__} want_object={want_obj}"
                        ),
                    )
                )

            if expect.json_required_keys:
                if not isinstance(parsed.value, dict):
                    results.append(
                        CheckResult(
                            name="json_required_keys",
                            passed=False,
                            detail=f"not an object (type={type(parsed.value).__name__})",
                        )
                    )
                else:
                    missing = [
                        key
                        for key in expect.json_required_keys
                        if key not in parsed.value
                    ]
                    results.append(
                        CheckResult(
                            name="json_required_keys",
                            passed=not missing,
                            detail="ok" if not missing else f"missing={missing!r}",
                        )
                    )

            if expect.json_equals is not None:
                # Total equality: parsed value must match the expected object exactly.
                passed = parsed.value == expect.json_equals
                results.append(
                    CheckResult(
                        name="json_equals",
                        passed=passed,
                        detail=(
                            "ok"
                            if passed
                            else f"got={parsed.value!r} want={expect.json_equals!r}"
                        ),
                    )
                )

    return results


def all_passed(results: list[CheckResult]) -> bool:
    return all(item.passed for item in results) if results else True
