"""Ollama adapter — speaks Ollama HTTP API behind the LLMBackend contract."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.backends.base import BackendError
from app.config import Settings


class OllamaBackend:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def base_url(self) -> str:
        return self._settings.ollama_base_url

    async def check_ready(self) -> tuple[bool, str]:
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.ready_check_timeout_seconds
            ) as client:
                response = await client.get(url)
                if response.status_code < 400:
                    return True, "backend reachable"
                return False, f"backend status {response.status_code}"
        except httpx.HTTPError as exc:
            return False, f"backend unreachable: {exc}"

    async def list_models(self) -> Any:
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.models_timeout_seconds
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise BackendError("timeout", f"Backend timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise BackendError(
                "backend_http",
                f"Backend error: {exc}",
                backend_status=exc.response.status_code,
                backend_body=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            raise BackendError(
                "connect", f"Backend connection error: {exc}"
            ) from exc

    async def generate(self, *, model: str, prompt: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.chat_timeout_seconds
            ) as client:
                response = await client.post(url, json=payload)
                if response.status_code >= 400:
                    raise BackendError(
                        "backend_http",
                        "Backend HTTP error",
                        backend_status=response.status_code,
                        backend_body=response.text,
                    )
                return response.json()
        except BackendError:
            raise
        except httpx.TimeoutException as exc:
            raise BackendError("timeout", f"Backend timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise BackendError(
                "connect", f"Backend connection error: {exc}"
            ) from exc

    async def stream_generate(
        self, *, model: str, prompt: str
    ) -> AsyncIterator[dict[str, Any]]:
        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": True}

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.chat_timeout_seconds
            ) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise BackendError(
                            "backend_http",
                            "Backend HTTP error",
                            backend_status=response.status_code,
                            backend_body=body.decode("utf-8", errors="replace"),
                        )

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            # Preserve opaque payloads for the gateway to forward.
                            yield {"_raw_line": line}
        except BackendError:
            raise
        except httpx.TimeoutException as exc:
            raise BackendError("timeout", f"Backend timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise BackendError(
                "connect", f"Backend connection error: {exc}"
            ) from exc
