"""Thin HTTP client for the inference gateway /chat endpoint."""

from __future__ import annotations

from typing import Any, Optional

import httpx


class GatewayError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def call_chat(
    *,
    base_url: str,
    prompt: str,
    model: Optional[str] = None,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    """
    POST /chat and return the JSON body.

    Raises GatewayError on transport/HTTP failures.
    """
    url = base_url.rstrip("/") + "/chat"
    payload: dict[str, Any] = {"prompt": prompt}
    if model:
        payload["model"] = model

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        raise GatewayError(f"gateway timeout: {exc}") from exc
    except httpx.RequestError as exc:
        raise GatewayError(f"gateway connection error: {exc}") from exc

    if response.status_code >= 400:
        raise GatewayError(
            f"gateway HTTP {response.status_code}: {response.text}",
            status_code=response.status_code,
        )

    return response.json()
