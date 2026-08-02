import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.backends import get_backend
from app.config import get_settings
from app.main import app


@pytest.fixture
def vllm_base_url() -> str:
    return "http://vllm:8000"


@pytest.fixture
def vllm_client(monkeypatch: pytest.MonkeyPatch, vllm_base_url: str):
    """Switch factory to VllmBackend for this test, then reset caches."""
    monkeypatch.setenv("BACKEND_TYPE", "vllm")
    monkeypatch.setenv("VLLM_BASE_URL", vllm_base_url)
    get_settings.cache_clear()
    get_backend.cache_clear()

    assert get_backend().name == "vllm"
    assert get_backend().base_url == vllm_base_url

    yield TestClient(app)

    get_settings.cache_clear()
    get_backend.cache_clear()


@respx.mock
def test_vllm_ready_and_chat_non_stream(vllm_client: TestClient, vllm_base_url: str):
    respx.get(f"{vllm_base_url}/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "mistral:7b"}]})
    )
    respx.post(f"{vllm_base_url}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "hola desde vllm"}}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )
    )

    ready = vllm_client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["backend"] == "vllm"
    assert ready.json()["backend_url"] == vllm_base_url

    chat = vllm_client.post(
        "/chat",
        json={"prompt": "hola", "model": "mistral:7b"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["backend"] == "vllm"
    assert body["response"] == "hola desde vllm"
    assert body["prompt_tokens"] == 5
    assert body["completion_tokens"] == 3

    sent = respx.calls.last.request
    assert str(sent.url) == f"{vllm_base_url}/v1/chat/completions"
    assert b'"stream":false' in sent.content


@respx.mock
def test_vllm_stream_sse_translated_to_ndjson(
    vllm_client: TestClient, vllm_base_url: str
):
    sse_body = "".join(
        [
            'data: {"choices":[{"delta":{"content":"Ho"}}]}\n',
            'data: {"choices":[{"delta":{"content":"la"}}]}\n',
            'data: {"choices":[{"delta":{}}],'
            '"usage":{"prompt_tokens":8,"completion_tokens":2}}\n',
            "data: [DONE]\n",
        ]
    )
    respx.post(f"{vllm_base_url}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            content=sse_body,
            headers={"content-type": "text/event-stream"},
        )
    )

    with vllm_client.stream(
        "POST",
        "/chat/stream",
        json={"prompt": "hola", "model": "mistral:7b"},
    ) as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line]

    events = [json.loads(line) for line in lines]
    assert events[0] == {"response": "Ho", "done": False}
    assert events[1] == {"response": "la", "done": False}
    assert events[2]["done"] is True
    assert events[2]["prompt_eval_count"] == 8
    assert events[2]["eval_count"] == 2

    metrics = vllm_client.get("/metrics").text
    assert "llm_ttft_seconds" in metrics
    assert "llm_tpot_seconds" in metrics

    sent = respx.calls.last.request
    assert b'"stream":true' in sent.content


@respx.mock
def test_vllm_connect_error(vllm_client: TestClient, vllm_base_url: str):
    respx.post(f"{vllm_base_url}/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    response = vllm_client.post(
        "/chat",
        json={"prompt": "hola", "model": "mistral:7b"},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["error_type"] == "connect"
