"""Backend adapters factory."""

from functools import lru_cache

from app.backends.base import BackendError, LLMBackend
from app.backends.ollama import OllamaBackend
from app.backends.vllm import VllmBackend
from app.config import get_settings


@lru_cache
def get_backend() -> LLMBackend:
    """
    Build the configured LLM backend.

    Selected by BACKEND_TYPE:
    - ollama → OllamaBackend (native Ollama HTTP)
    - vllm   → VllmBackend (OpenAI-compatible HTTP/SSE)
    """
    settings = get_settings()
    backend_type = settings.backend_type.lower().strip()

    if backend_type == "ollama":
        return OllamaBackend(settings)
    if backend_type == "vllm":
        return VllmBackend(settings)

    raise ValueError(
        f"Unsupported BACKEND_TYPE={settings.backend_type!r}. "
        "Supported: ollama, vllm"
    )


__all__ = [
    "BackendError",
    "LLMBackend",
    "OllamaBackend",
    "VllmBackend",
    "get_backend",
]
