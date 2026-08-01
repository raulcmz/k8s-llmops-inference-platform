import json

import httpx
import respx
from fastapi.testclient import TestClient


def test_health_is_process_only(client: TestClient):
    """Liveness must succeed even if the LLM backend is down."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@respx.mock
def test_ready_ok_when_backend_reachable(client: TestClient, backend_url: str):
    respx.get(f"{backend_url}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["backend"] == "ollama"
    assert body["backend_url"] == backend_url


@respx.mock
def test_ready_503_when_backend_unreachable(client: TestClient, backend_url: str):
    respx.get(f"{backend_url}/api/tags").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["backend_url"] == backend_url
    assert "detail" in body


@respx.mock
def test_models_ok(client: TestClient, backend_url: str):
    payload = {"models": [{"name": "mistral:7b"}]}
    respx.get(f"{backend_url}/api/tags").mock(
        return_value=httpx.Response(200, json=payload)
    )

    response = client.get("/models")

    assert response.status_code == 200
    assert response.json() == payload


@respx.mock
def test_models_502_on_backend_error(client: TestClient, backend_url: str):
    respx.get(f"{backend_url}/api/tags").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    response = client.get("/models")

    assert response.status_code == 502
    assert "Backend error" in response.json()["detail"]


@respx.mock
def test_chat_ok_uses_default_model(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={"response": "hola"},
        )
    )

    response = client.post("/chat", json={"prompt": "di hola"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "hola"
    assert body["model"] == "mistral:7b"
    assert body["backend"] == "ollama"
    assert "latency_ms" in body

    assert respx.calls.call_count == 1
    sent = respx.calls.last.request
    assert sent.url == f"{backend_url}/api/generate"
    assert b'"model":"mistral:7b"' in sent.content


@respx.mock
def test_chat_ok_with_explicit_model(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "ok"})
    )

    response = client.post(
        "/chat",
        json={"prompt": "test", "model": "granite3.1-moe:3b"},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "granite3.1-moe:3b"
    assert b'"model":"granite3.1-moe:3b"' in respx.calls.last.request.content


@respx.mock
def test_chat_exposes_backend_token_and_timing_stats(
    client: TestClient, backend_url: str
):
    """Non-stream Ollama stats are surfaced honestly (not as TTFT)."""
    respx.post(f"{backend_url}/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": "hola",
                "prompt_eval_count": 12,
                "eval_count": 4,
                "prompt_eval_duration": 100_000_000,
                "eval_duration": 250_000_000,
                "total_duration": 400_000_000,
            },
        )
    )

    response = client.post("/chat", json={"prompt": "di hola"})

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_tokens"] == 12
    assert body["completion_tokens"] == 4
    assert body["backend_prompt_eval_ms"] == 100.0
    assert body["backend_eval_ms"] == 250.0
    assert body["backend_total_ms"] == 400.0

    metrics = client.get("/metrics").text
    assert "llm_prompt_tokens_total" in metrics
    assert "llm_completion_tokens_total" in metrics
    assert "llm_request_duration_seconds" in metrics
    assert "llm_backend_prompt_eval_seconds" in metrics


@respx.mock
def test_chat_502_when_backend_returns_error(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        return_value=httpx.Response(500, text="boom")
    )

    response = client.post("/chat", json={"prompt": "hola"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["backend_status"] == 500
    assert detail["error_type"] == "backend_http"

    metrics = client.get("/metrics").text
    assert 'error_type="backend_http"' in metrics
    assert 'mode="non_stream"' in metrics


@respx.mock
def test_chat_502_when_backend_unreachable(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    response = client.post("/chat", json={"prompt": "hola"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_type"] == "connect"
    assert "Backend connection error" in detail["message"]

    metrics = client.get("/metrics").text
    assert 'error_type="connect"' in metrics


@respx.mock
def test_chat_502_on_timeout(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    response = client.post("/chat", json={"prompt": "hola"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_type"] == "timeout"

    metrics = client.get("/metrics").text
    assert 'error_type="timeout"' in metrics


def _ollama_stream_body() -> str:
    return "".join(
        [
            json.dumps({"response": "Ho", "done": False}) + "\n",
            json.dumps({"response": "la", "done": False}) + "\n",
            json.dumps(
                {
                    "response": "",
                    "done": True,
                    "prompt_eval_count": 8,
                    "eval_count": 2,
                    "prompt_eval_duration": 50_000_000,
                    "eval_duration": 100_000_000,
                    "total_duration": 180_000_000,
                }
            )
            + "\n",
        ]
    )


@respx.mock
def test_chat_stream_ndjson_and_ttft_tpot_metrics(
    client: TestClient, backend_url: str
):
    respx.post(f"{backend_url}/api/generate").mock(
        return_value=httpx.Response(
            200,
            content=_ollama_stream_body(),
            headers={"content-type": "application/x-ndjson"},
        )
    )

    with client.stream("POST", "/chat/stream", json={"prompt": "hola"}) as response:
        assert response.status_code == 200
        assert "application/x-ndjson" in response.headers["content-type"]
        lines = [line for line in response.iter_lines() if line]

    assert len(lines) == 3
    assert json.loads(lines[0])["response"] == "Ho"
    assert json.loads(lines[1])["response"] == "la"
    assert json.loads(lines[2])["done"] is True

    sent = respx.calls.last.request
    assert b'"stream":true' in sent.content or b'"stream": true' in sent.content

    metrics = client.get("/metrics").text
    assert "llm_ttft_seconds" in metrics
    assert "llm_tpot_seconds" in metrics
    assert 'mode="stream"' in metrics


@respx.mock
def test_chat_stream_connect_error_line(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with client.stream("POST", "/chat/stream", json={"prompt": "hola"}) as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line]

    payload = json.loads(lines[-1])
    assert payload["error"] is True
    assert payload["error_type"] == "connect"

    metrics = client.get("/metrics").text
    assert 'error_type="connect"' in metrics
    assert 'mode="stream"' in metrics
