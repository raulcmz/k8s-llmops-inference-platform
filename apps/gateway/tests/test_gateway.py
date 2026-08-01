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
def test_chat_502_when_backend_returns_error(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        return_value=httpx.Response(500, text="boom")
    )

    response = client.post("/chat", json={"prompt": "hola"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["backend_status"] == 500


@respx.mock
def test_chat_502_when_backend_unreachable(client: TestClient, backend_url: str):
    respx.post(f"{backend_url}/api/generate").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    response = client.post("/chat", json={"prompt": "hola"})

    assert response.status_code == 502
    assert "Backend connection error" in response.json()["detail"]
