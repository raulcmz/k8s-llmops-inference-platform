"""LLM backend contract used by the gateway.

The gateway (HTTP, probes, Prometheus) depends on this Protocol — not on
Ollama/vLLM specifics. That is the Adapter pattern: swap engines without
rewriting /chat handlers.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional, Protocol


class BackendError(Exception):
    """Transport/application failure talking to an LLM engine."""

    def __init__(
        self,
        error_type: str,
        message: str,
        *,
        backend_status: Optional[int] = None,
        backend_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.backend_status = backend_status
        self.backend_body = backend_body


class LLMBackend(Protocol):
    """Minimal interface every inference engine adapter must implement."""

    @property
    def name(self) -> str:
        """Short backend id used in API payloads and metrics labels later."""
        ...

    @property
    def base_url(self) -> str:
        """Base URL the adapter talks to (shown on /ready for debugging)."""
        ...

    async def check_ready(self) -> tuple[bool, str]:
        """Return (ok, detail) for readiness probes."""
        ...

    async def list_models(self) -> Any:
        """Return the backend-native model listing payload."""
        ...

    async def generate(self, *, model: str, prompt: str) -> dict[str, Any]:
        """Non-streaming completion. Raises BackendError on failure."""
        ...

    def stream_generate(
        self, *, model: str, prompt: str
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Streaming completion as an async iterator of JSON objects.

        For Ollama this is the parsed NDJSON objects (including the final
        done=true object). Raises BackendError if the stream cannot start.
        """
        ...
