import json

import httpx
import respx

from benchmarks.harness.stream_client import run_stream_sample


@respx.mock
def test_run_stream_sample_measures_ttft():
    def stream_response(request):
        lines = [
            json.dumps({"response": "Ho", "done": False}),
            json.dumps({"response": "la", "done": False}),
            json.dumps(
                {
                    "response": "",
                    "done": True,
                    "completion_tokens": 3,
                    "prompt_tokens": 5,
                }
            ),
        ]
        content = ("\n".join(lines) + "\n").encode()
        return httpx.Response(200, content=content)

    respx.post("http://bench.test/chat/stream").mock(side_effect=stream_response)

    sample = run_stream_sample(
        base_url="http://bench.test",
        case_id="c1",
        prompt="hola",
    )
    assert sample.ok is True
    assert sample.ttft_seconds is not None
    assert sample.ttft_seconds >= 0
    assert sample.tpot_seconds is not None
    assert sample.completion_tokens == 3
    assert sample.chunks_with_text == 2
    assert "Ho" in sample.response_preview
