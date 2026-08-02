"""Automatic checks against model output (no LLM-as-judge yet)."""

from __future__ import annotations

from dataclasses import dataclass

from evals.harness.cases import Expectation


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


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

    return results


def all_passed(results: list[CheckResult]) -> bool:
    return all(item.passed for item in results) if results else True
