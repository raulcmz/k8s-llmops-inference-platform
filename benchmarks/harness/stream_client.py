"""Streaming client for gateway /chat/stream (NDJSON) with client-side TTFT/TPOT."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx


class BenchClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class StreamSample:
    """One streaming request measured on the client."""

    case_id: str
    model: Optional[str]
    prompt: str
    ok: bool
    error: Optional[str]
    e2e_seconds: Optional[float]
    ttft_seconds: Optional[float]
    tpot_seconds: Optional[float]
    completion_tokens: Optional[int]
    prompt_tokens: Optional[int]
    chunks_with_text: int
    response_preview: str


def run_stream_sample(
    *,
    base_url: str,
    case_id: str,
    prompt: str,
    model: Optional[str] = None,
    timeout_seconds: float = 180.0,
) -> StreamSample:
    """
    POST /chat/stream and measure:

    - TTFT: time until first NDJSON object with non-empty \"response\"
    - TPOT: (t_last - t_first) / (completion_tokens - 1) when tokens >= 2
      else (t_last - t_first) / (chunks_with_text - 1) when chunks >= 2
    - E2E: wall time of the full stream
    """
    url = base_url.rstrip("/") + "/chat/stream"
    payload: dict[str, Any] = {"prompt": prompt}
    if model:
        payload["model"] = model

    start = time.perf_counter()
    first_token_at: Optional[float] = None
    last_token_at: Optional[float] = None
    chunks_with_text = 0
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    text_parts: list[str] = []
    error: Optional[str] = None

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            with client.stream("POST", url, json=payload) as response:
                if response.status_code >= 400:
                    body = response.read().decode("utf-8", errors="replace")
                    raise BenchClientError(
                        f"gateway HTTP {response.status_code}: {body}",
                        status_code=response.status_code,
                    )
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        error = str(data.get("message") or data)
                        break
                    chunk = data.get("response") or ""
                    now = time.perf_counter()
                    if chunk:
                        chunks_with_text += 1
                        text_parts.append(chunk)
                        if first_token_at is None:
                            first_token_at = now
                        last_token_at = now
                    if data.get("done"):
                        completion_tokens = data.get("completion_tokens")
                        prompt_tokens = data.get("prompt_tokens")
                        if isinstance(completion_tokens, bool):
                            completion_tokens = None
                        if isinstance(prompt_tokens, bool):
                            prompt_tokens = None
    except httpx.TimeoutException as exc:
        raise BenchClientError(f"gateway timeout: {exc}") from exc
    except httpx.RequestError as exc:
        raise BenchClientError(f"gateway connection error: {exc}") from exc

    end = time.perf_counter()
    e2e = end - start
    ttft = (first_token_at - start) if first_token_at is not None else None

    tpot: Optional[float] = None
    if first_token_at is not None and last_token_at is not None:
        span = last_token_at - first_token_at
        if isinstance(completion_tokens, int) and completion_tokens >= 2:
            tpot = span / (completion_tokens - 1)
        elif chunks_with_text >= 2:
            tpot = span / (chunks_with_text - 1)

    preview = "".join(text_parts)
    if len(preview) > 240:
        preview = preview[:240] + "…"

    return StreamSample(
        case_id=case_id,
        model=model,
        prompt=prompt,
        ok=error is None and first_token_at is not None,
        error=error,
        e2e_seconds=round(e2e, 4),
        ttft_seconds=round(ttft, 4) if ttft is not None else None,
        tpot_seconds=round(tpot, 6) if tpot is not None else None,
        completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        chunks_with_text=chunks_with_text,
        response_preview=preview,
    )
