"""Backend adapters factory."""

from functools import lru_cache

from app.backends.base import BackendError, LLMBackend
from app.backends.ollama import OllamaBackend
from app.config import get_settings


@lru_cache
def get_backend() -> LLMBackend:
    """
    Build the configured LLM backend.

    Today only Ollama is implemented. H3-T2 adds a vLLM adapter selected by
    BACKEND_TYPE=vllm without changing /chat handlers.
    """
    settings = get_settings()
    backend_type = settings.backend_type.lower().strip()

    if backend_type == "ollama":
        return OllamaBackend(settings)

    raise ValueError(
        f"Unsupported BACKEND_TYPE={settings.backend_type!r}. "
        "Supported: ollama"
    )


__all__ = ["BackendError", "LLMBackend", "OllamaBackend", "get_backend"]
