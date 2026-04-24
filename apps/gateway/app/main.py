import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "mistral:7b")


app = FastAPI(
    title="Internal LLM Gateway",
    description="A Kubernetes-native internal gateway for LLM backends.",
    version="0.1.0",
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: Optional[str] = None


class ChatResponse(BaseModel):
    model: str
    response: str
    latency_ms: float
    backend: str = "ollama"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models")
async def models():
    url = f"{OLLAMA_BASE_URL}/api/tags"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Backend error: {exc}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    model = request.model or DEFAULT_MODEL
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": model,
        "prompt": request.prompt,
        "stream": False,
    }

    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload)

            if response.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "backend_status": response.status_code,
                        "backend_body": response.text,
                    },
                )

            data = response.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Backend connection error: {exc}")

    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return ChatResponse(
        model=model,
        response=data.get("response", ""),
        latency_ms=latency_ms,
    )
