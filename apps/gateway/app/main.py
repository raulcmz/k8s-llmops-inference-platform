import json
import time
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest

from app.backends import BackendError, get_backend
from app.config import get_settings


settings = get_settings()
backend = get_backend()

REQUEST_COUNT = Counter(
    "llm_requests_total",
    "Total LLM chat requests received by the gateway",
    ["model", "mode"],
)

ERROR_COUNT = Counter(
    "llm_errors_total",
    "Total LLM chat errors classified by type",
    ["error_type", "mode"],
)

# End-to-end gateway latency (client → gateway → backend → gateway).
# Non-streaming only. True TTFT is llm_ttft_seconds on /chat/stream.
REQUEST_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "End-to-end /chat latency in seconds (non-streaming)",
    ["model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

PROMPT_TOKENS = Counter(
    "llm_prompt_tokens_total",
    "Prompt tokens reported by the backend",
    ["model", "mode"],
)

COMPLETION_TOKENS = Counter(
    "llm_completion_tokens_total",
    "Completion tokens reported by the backend",
    ["model", "mode"],
)

BACKEND_PROMPT_EVAL = Histogram(
    "llm_backend_prompt_eval_seconds",
    "Backend-reported prompt evaluation duration (Ollama prompt_eval_duration)",
    ["model", "mode"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

BACKEND_EVAL = Histogram(
    "llm_backend_eval_seconds",
    "Backend-reported generation duration (Ollama eval_duration)",
    ["model", "mode"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

BACKEND_TOTAL = Histogram(
    "llm_backend_total_seconds",
    "Backend-reported total duration (Ollama total_duration)",
    ["model", "mode"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

TTFT = Histogram(
    "llm_ttft_seconds",
    "Time to first token for streaming /chat/stream",
    ["model"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

TPOT = Histogram(
    "llm_tpot_seconds",
    "Average time per output token after the first token (streaming)",
    ["model"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


app = FastAPI(
    title="Internal LLM Gateway",
    description="A Kubernetes-native internal gateway for LLM backends.",
    version="0.5.0",
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: Optional[str] = None


class ChatResponse(BaseModel):
    model: str
    response: str
    # Gateway-measured end-to-end latency (not TTFT).
    latency_ms: float
    backend: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    # Durations reported by the engine (Ollama nanoseconds converted to ms).
    backend_total_ms: Optional[float] = None
    backend_prompt_eval_ms: Optional[float] = None
    backend_eval_ms: Optional[float] = None


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    backend: str
    backend_url: str


def _ns_to_ms(value_ns: Any) -> Optional[float]:
    if value_ns is None:
        return None
    try:
        return round(float(value_ns) / 1_000_000.0, 2)
    except (TypeError, ValueError):
        return None


def _ns_to_seconds(value_ns: Any) -> Optional[float]:
    if value_ns is None:
        return None
    try:
        return float(value_ns) / 1_000_000_000.0
    except (TypeError, ValueError):
        return None


def _record_backend_stats(
    model: str, data: dict[str, Any], mode: str
) -> dict[str, Any]:
    """Extract engine stats and update Prometheus counters/histograms."""
    prompt_tokens = data.get("prompt_eval_count")
    completion_tokens = data.get("eval_count")

    if isinstance(prompt_tokens, int):
        PROMPT_TOKENS.labels(model=model, mode=mode).inc(prompt_tokens)
    if isinstance(completion_tokens, int):
        COMPLETION_TOKENS.labels(model=model, mode=mode).inc(completion_tokens)

    prompt_eval_s = _ns_to_seconds(data.get("prompt_eval_duration"))
    eval_s = _ns_to_seconds(data.get("eval_duration"))
    total_s = _ns_to_seconds(data.get("total_duration"))

    if prompt_eval_s is not None:
        BACKEND_PROMPT_EVAL.labels(model=model, mode=mode).observe(prompt_eval_s)
    if eval_s is not None:
        BACKEND_EVAL.labels(model=model, mode=mode).observe(eval_s)
    if total_s is not None:
        BACKEND_TOTAL.labels(model=model, mode=mode).observe(total_s)

    return {
        "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
        "completion_tokens": (
            completion_tokens if isinstance(completion_tokens, int) else None
        ),
        "backend_total_ms": _ns_to_ms(data.get("total_duration")),
        "backend_prompt_eval_ms": _ns_to_ms(data.get("prompt_eval_duration")),
        "backend_eval_ms": _ns_to_ms(data.get("eval_duration")),
    }


def _http_error_from_backend(exc: BackendError) -> HTTPException:
    detail: dict[str, Any] = {
        "message": exc.message,
        "error_type": exc.error_type,
    }
    if exc.backend_status is not None:
        detail["backend_status"] = exc.backend_status
    if exc.backend_body is not None:
        detail["backend_body"] = exc.backend_body
    return HTTPException(status_code=502, detail=detail)


@app.get("/health", response_model=HealthResponse)
def health():
    """Liveness: process is up. Does not check the LLM backend."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadyResponse)
async def ready():
    """Readiness: gateway can accept traffic only if the backend responds."""
    ok, detail = await backend.check_ready()
    if not ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "backend": backend.name,
                "backend_url": backend.base_url,
                "detail": detail,
            },
        )
    return ReadyResponse(
        status="ready",
        backend=backend.name,
        backend_url=backend.base_url,
    )


@app.get("/models")
async def models():
    try:
        return await backend.list_models()
    except BackendError as exc:
        raise _http_error_from_backend(exc) from exc


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    model = request.model or settings.default_model
    mode = "non_stream"

    REQUEST_COUNT.labels(model=model, mode=mode).inc()

    start = time.perf_counter()
    data: dict[str, Any] = {}

    try:
        data = await backend.generate(model=model, prompt=request.prompt)
    except BackendError as exc:
        ERROR_COUNT.labels(error_type=exc.error_type, mode=mode).inc()
        raise _http_error_from_backend(exc) from exc
    finally:
        REQUEST_LATENCY.labels(model=model).observe(time.perf_counter() - start)

    stats = _record_backend_stats(model, data, mode=mode)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return ChatResponse(
        model=model,
        response=data.get("response", ""),
        latency_ms=latency_ms,
        backend=backend.name,
        prompt_tokens=stats["prompt_tokens"],
        completion_tokens=stats["completion_tokens"],
        backend_total_ms=stats["backend_total_ms"],
        backend_prompt_eval_ms=stats["backend_prompt_eval_ms"],
        backend_eval_ms=stats["backend_eval_ms"],
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat completions as NDJSON via the configured LLMBackend.

    The gateway measures:
    - TTFT: time until the first chunk with a non-empty "response"
    - TPOT: (t_last - t_first) / (completion_tokens - 1) when tokens >= 2
    """
    model = request.model or settings.default_model
    mode = "stream"

    REQUEST_COUNT.labels(model=model, mode=mode).inc()

    async def event_generator() -> AsyncIterator[str]:
        start = time.perf_counter()
        first_token_at: Optional[float] = None
        last_token_at: Optional[float] = None
        final_stats: dict[str, Any] = {}

        try:
            async for data in backend.stream_generate(
                model=model, prompt=request.prompt
            ):
                if "_raw_line" in data:
                    yield data["_raw_line"] + "\n"
                    continue

                chunk = data.get("response") or ""
                now = time.perf_counter()
                if chunk:
                    if first_token_at is None:
                        first_token_at = now
                        TTFT.labels(model=model).observe(now - start)
                    last_token_at = now

                if data.get("done"):
                    final_stats = data

                yield json.dumps(data) + "\n"

        except BackendError as exc:
            ERROR_COUNT.labels(error_type=exc.error_type, mode=mode).inc()
            payload: dict[str, Any] = {
                "error": True,
                "error_type": exc.error_type,
                "message": exc.message,
            }
            if exc.backend_status is not None:
                payload["backend_status"] = exc.backend_status
            if exc.backend_body is not None:
                payload["backend_body"] = exc.backend_body
            yield json.dumps(payload) + "\n"
            return

        if final_stats:
            stats = _record_backend_stats(model, final_stats, mode=mode)
            completion_tokens = stats["completion_tokens"]
            if (
                first_token_at is not None
                and last_token_at is not None
                and isinstance(completion_tokens, int)
                and completion_tokens >= 2
            ):
                tpot = (last_token_at - first_token_at) / (completion_tokens - 1)
                TPOT.labels(model=model).observe(tpot)

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
