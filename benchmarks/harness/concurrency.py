"""Run several chat requests at the same time (concurrency).

Beginner picture:
  concurrency=1 → one question at a time (a queue of one)
  concurrency=4 → up to four questions in flight together

That stresses the model server the way real users do when several
people chat at once.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from benchmarks.harness.stream_client import (
    BenchClientError,
    StreamSample,
    run_stream_sample,
)


def parse_concurrency_list(raw: str) -> list[int]:
    """
    Parse a string like \"1,2,4\" into [1, 2, 4].

    Rejects empty values and numbers < 1.
    """
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value < 1:
            raise ValueError(f"concurrency must be >= 1, got {value}")
        values.append(value)
    if not values:
        raise ValueError("concurrency list is empty")
    return values


def _failed_sample(
    *,
    case_id: str,
    prompt: str,
    model: Optional[str],
    error: str,
) -> StreamSample:
    return StreamSample(
        case_id=case_id,
        model=model,
        prompt=prompt,
        ok=False,
        error=error,
        e2e_seconds=None,
        ttft_seconds=None,
        tpot_seconds=None,
        completion_tokens=None,
        prompt_tokens=None,
        chunks_with_text=0,
        response_preview="",
    )


def run_one_request(
    *,
    base_url: str,
    case_id: str,
    prompt: str,
    model: Optional[str],
    timeout_seconds: float,
    request_index: int,
) -> StreamSample:
    label = f"{case_id}#{request_index}"
    try:
        return run_stream_sample(
            base_url=base_url,
            case_id=label,
            prompt=prompt,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    except BenchClientError as exc:
        return _failed_sample(
            case_id=label,
            prompt=prompt,
            model=model,
            error=str(exc),
        )


def run_concurrency_level(
    *,
    base_url: str,
    case_id: str,
    prompt: str,
    model: Optional[str],
    concurrency: int,
    requests_per_level: int,
    timeout_seconds: float,
) -> tuple[list[StreamSample], float]:
    """
    Send `requests_per_level` requests, with at most `concurrency` in parallel.

    Returns (samples, wall_seconds) where wall_seconds is the clock time
    from starting the batch until the last request finishes.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if requests_per_level < 1:
        raise ValueError("requests_per_level must be >= 1")

    wall_start = time.perf_counter()
    samples: list[StreamSample] = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(
                run_one_request,
                base_url=base_url,
                case_id=case_id,
                prompt=prompt,
                model=model,
                timeout_seconds=timeout_seconds,
                request_index=index,
            )
            for index in range(1, requests_per_level + 1)
        ]
        for future in as_completed(futures):
            samples.append(future.result())

    wall_seconds = time.perf_counter() - wall_start
    # Keep a stable order in the report (by case label).
    samples.sort(key=lambda item: item.case_id)
    return samples, wall_seconds
