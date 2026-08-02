"""vLLM adapter — OpenAI-compatible HTTP API behind LLMBackend.

Anti-corruption layer: translates OpenAI/vLLM JSON (+ SSE streams) into the
gateway's internal event shape (Ollama-like dicts with response/done/tokens)
so /chat handlers and Prometheus code stay backend-agnostic.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

import httpx

from app.backends.base import BackendError
from app.config import Settings


class VllmBackend:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "vllm"

    @property
    def base_url(self) -> str:
        return self._settings.vllm_base_url.rstrip("/")

    async def check_ready(self) -> tuple[bool, str]:
        url = f"{self.base_url}/v1/models"
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
        url = f"{self.base_url}/v1/models"
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
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
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
                return self._to_gateway_completion(response.json())
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
        """
        Consume vLLM SSE (`data: {...}`) and yield gateway NDJSON objects.
        """
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            # Ask for usage on the final chunk when the server supports it.
            "stream_options": {"include_usage": True},
        }

        usage: dict[str, Any] = {}
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
                        if not line.startswith("data:"):
                            continue

                        data_str = line[len("data:") :].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            yield {"_raw_line": line}
                            continue

                        if event.get("usage"):
                            usage = event["usage"]

                        delta = self._extract_delta_text(event)
                        if delta:
                            yield {"response": delta, "done": False}

        except BackendError:
            raise
        except httpx.TimeoutException as exc:
            raise BackendError("timeout", f"Backend timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise BackendError(
                "connect", f"Backend connection error: {exc}"
            ) from exc

        yield {
            "response": "",
            "done": True,
            "prompt_eval_count": usage.get("prompt_tokens"),
            "eval_count": usage.get("completion_tokens"),
        }

    @staticmethod
    def _extract_delta_text(event: dict[str, Any]) -> str:
        choices = event.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        return content if isinstance(content, str) else ""

    @staticmethod
    def _to_gateway_completion(payload: dict[str, Any]) -> dict[str, Any]:
        choices = payload.get("choices") or []
        text = ""
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                text = content

        usage = payload.get("usage") or {}
        prompt_tokens: Optional[int] = usage.get("prompt_tokens")
        completion_tokens: Optional[int] = usage.get("completion_tokens")

        return {
            "response": text,
            "prompt_eval_count": prompt_tokens
            if isinstance(prompt_tokens, int)
            else None,
            "eval_count": completion_tokens
            if isinstance(completion_tokens, int)
            else None,
        }
