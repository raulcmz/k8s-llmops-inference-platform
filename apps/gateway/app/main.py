import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest

from app.config import get_settings


settings = get_settings()

REQUEST_COUNT = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["model"],
)

ERROR_COUNT = Counter(
    "llm_errors_total",
    "Total LLM errors",
)

REQUEST_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "LLM request latency",
)


app = FastAPI(
    title="Internal LLM Gateway",
    description="A Kubernetes-native internal gateway for LLM backends.",
    version="0.2.1",
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: Optional[str] = None


class ChatResponse(BaseModel):
    model: str
    response: str
    latency_ms: float
    backend: str = "ollama"


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    backend: str
    backend_url: str


async def backend_is_reachable() -> tuple[bool, str]:
    """Return (ok, detail) for a lightweight backend readiness check."""
    url = f"{settings.ollama_base_url}/api/tags"
    try:
        async with httpx.AsyncClient(
            timeout=settings.ready_check_timeout_seconds
        ) as client:
            response = await client.get(url)
            if response.status_code < 400:
                return True, "backend reachable"
            return False, f"backend status {response.status_code}"
    except httpx.HTTPError as exc:
        return False, f"backend unreachable: {exc}"


@app.get("/health", response_model=HealthResponse)
def health():
    """Liveness: process is up. Does not check the LLM backend."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadyResponse)
async def ready():
    """Readiness: gateway can accept traffic only if the backend responds."""
    ok, detail = await backend_is_reachable()
    if not ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "backend": "ollama",
                "backend_url": settings.ollama_base_url,
                "detail": detail,
            },
        )
    return ReadyResponse(
        status="ready",
        backend="ollama",
        backend_url=settings.ollama_base_url,
    )


@app.get("/models")
async def models():
    url = f"{settings.ollama_base_url}/api/tags"

    try:
        async with httpx.AsyncClient(timeout=settings.models_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Backend error: {exc}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    model = request.model or settings.default_model
    url = f"{settings.ollama_base_url}/api/generate"

    REQUEST_COUNT.labels(model=model).inc()

    payload = {
        "model": model,
        "prompt": request.prompt,
        "stream": False,
    }

    start = time.perf_counter()

    try:
        with REQUEST_LATENCY.time():
            async with httpx.AsyncClient(timeout=settings.chat_timeout_seconds) as client:
                response = await client.post(url, json=payload)

                if response.status_code >= 400:
                    ERROR_COUNT.inc()
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "backend_status": response.status_code,
                            "backend_body": response.text,
                        },
                    )

                data = response.json()

    except httpx.RequestError as exc:
        ERROR_COUNT.inc()
        raise HTTPException(
            status_code=502,
            detail=f"Backend connection error: {exc}",
        )

    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return ChatResponse(
        model=model,
        response=data.get("response", ""),
        latency_ms=latency_ms,
    )


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
