# K8s LLMOps Inference Platform

Lab project: an **internal LLM inference gateway** on Kubernetes that fronts a remote model server (today: **Ollama** outside the cluster).

This is a **foundation for LLMOps experimentation**, not a full production LLM platform. The focus is platform engineering patterns around LLM serving: stable API edge, health semantics, config-as-env, tests, CI, and K8s probes.

## What it is (today)

```text
Client (curl / other services)
        ↓
Internal LLM Gateway (FastAPI :8080)
  /health       → liveness (process only)
  /ready        → readiness (backend reachable)
  /models       → proxy to Ollama tags
  /chat         → non-streaming generate (JSON)
  /chat/stream  → streaming generate (NDJSON)
  /metrics      → Prometheus metrics
        ↓
Ollama on a lab host (Windows) :11434
        ↓
Local models (e.g. mistral:7b)
```

### Included

| Area | Status |
|---|---|
| FastAPI gateway | Done |
| Split `/health` vs `/ready` | Done |
| Config via env (`pydantic-settings`) | Done |
| Non-stream `/chat` + stream `/chat/stream` (NDJSON) | Done |
| Prometheus metrics (E2E, tokens, errors, TTFT/TPOT) | Done |
| Unit tests with mocked backend (`pytest` + `respx`) | Done |
| GitHub Actions CI on gateway changes | Done |
| K8s Deployment probes + ConfigMap | Done |
| Ollama via manual Service/Endpoints (lab) | Done |

### Explicitly not included yet

- Live vLLM deployment manifests / GPU runbooks (adapter code is ready; cluster/GPU optional)
- Auth, rate limiting, TLS
- Autoscaling / HA beyond a single replica demo
- Evaluation / human-feedback loop
- MLflow / MinIO benchmark artifact store
- Published benchmark tables with controlled GPU runs

## Repository layout

```text
apps/gateway/          # FastAPI app, Dockerfile, tests, requirements
k8s/gateway/           # Deployment, Service, ConfigMap, ServiceMonitor
k8s/ollama-backend/    # Lab Service + Endpoints → Windows host IP
.github/workflows/     # CI (pytest)
```

## Quick start (no Kubernetes)

Typical lab: **Ollama on Windows**, gateway on an **Ubuntu VM**.

```bash
cd apps/gateway
python3 -m venv .venv
source .venv/bin/activate
# or: uv pip install -r requirements.txt
pip install -r requirements.txt

export OLLAMA_BASE_URL=http://<WINDOWS_HOST_IP>:11434
export DEFAULT_MODEL=mistral:7b

uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Smoke checks:

```bash
curl -s http://127.0.0.1:8080/health
curl -s -i http://127.0.0.1:8080/ready
curl -s http://127.0.0.1:8080/models

# Non-stream (single JSON response)
curl -s http://127.0.0.1:8080/chat \
  -H 'content-type: application/json' \
  -d '{"prompt":"hola en una frase"}'

# Stream (NDJSON lines; -N disables curl buffering)
curl -N http://127.0.0.1:8080/chat/stream \
  -H 'content-type: application/json' \
  -d '{"prompt":"hola en una frase"}'

curl -s http://127.0.0.1:8080/metrics | rg 'llm_'
```

Expected:

- `/health` → `200` if the process is up
- `/ready` → `200` if Ollama answers; `503` if not
- Stopping Ollama should flip `/ready` to `503` without killing `/health`
- `/chat/stream` prints one JSON object per line until `"done": true`

## Metrics (Prometheus `/metrics`)

All series are exposed by the gateway. Labels commonly include `model` and, where relevant, `mode=non_stream|stream`.

| Metric | What it measures | When it is recorded |
|---|---|---|
| `llm_requests_total` | Chat requests received | `/chat` and `/chat/stream` |
| `llm_errors_total{error_type=...}` | Classified failures: `connect`, `timeout`, `backend_http` | Failed chat attempts |
| `llm_request_duration_seconds` | **End-to-end** latency of non-stream `/chat` | `/chat` only |
| `llm_prompt_tokens_total` / `llm_completion_tokens_total` | Tokens reported by Ollama | When Ollama returns counts |
| `llm_backend_prompt_eval_seconds` | Ollama `prompt_eval_duration` | When present in Ollama payload |
| `llm_backend_eval_seconds` | Ollama `eval_duration` | When present |
| `llm_backend_total_seconds` | Ollama `total_duration` | When present |
| `llm_ttft_seconds` | **Time to first token** (first non-empty `response` chunk) | `/chat/stream` only |
| `llm_tpot_seconds` | Avg time per output token after the first (`(t_last-t_first)/(n-1)`, `n>=2`) | `/chat/stream` only |

### Honest naming notes

- **E2E ≠ TTFT.** `llm_request_duration_seconds` is full request time for non-stream `/chat`. It is **not** time-to-first-token.
- **TTFT/TPOT require streaming.** They are only measured on `/chat/stream`.
- **Backend `*_seconds` histograms** come from Ollama’s own nanosecond timers (converted), not from gateway wall-clock TTFT.
- Lab CPU runs often show high TTFT (seconds) and modest TPOT; that is expected without a dedicated GPU.

### Example lab observation (CPU, `mistral:7b`)

One local streaming request produced roughly:

- TTFT ≈ 9.6s (`llm_ttft_seconds_sum`)
- TPOT ≈ 0.14s/token (`llm_tpot_seconds_sum`)

Numbers vary with host load, model size, and whether the model is already warm in Ollama.

## Tests & CI

```bash
cd apps/gateway
pip install -r requirements-dev.txt
python -m pytest -v
```

Tests mock Ollama with `respx` — no GPU and no live backend required.  
CI runs the same suite on pull requests / pushes that touch `apps/gateway/**` (see `.github/workflows/ci.yml`).

## Kubernetes (lab)

See [`k8s/README.md`](k8s/README.md) for apply order.

Important lab caveats:

1. `k8s/ollama-backend/endpoints.yaml` points at a **host IP** (VMware/Windows). Update it when the IP changes (DHCP). This is not a production service-discovery pattern.
2. For local (non-K8s) runs, always set `OLLAMA_BASE_URL` to the current Windows host IP; the default `http://ollama:11434` only resolves inside the cluster.
3. `Deployment` image `rcabe005/llm-gateway:0.1.1` may lag `main` (streaming/metrics). Rebuild/push before relying on new endpoints in-cluster.
4. Optional `ServiceMonitor` only works if Prometheus Operator is installed.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `BACKEND_TYPE` | `ollama` | LLM adapter: `ollama` or `vllm` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Used when `BACKEND_TYPE=ollama` |
| `VLLM_BASE_URL` | `http://vllm:8000` | Used when `BACKEND_TYPE=vllm` (OpenAI-compatible) |
| `DEFAULT_MODEL` | `mistral:7b` | Model when request omits `model` |
| `READY_CHECK_TIMEOUT_SECONDS` | `2` | Readiness probe budget |
| `MODELS_TIMEOUT_SECONDS` | `10` | `/models` timeout |
| `CHAT_TIMEOUT_SECONDS` | `120` | `/chat` and `/chat/stream` timeout |

In cluster, these are provided by `k8s/gateway/configmap.yaml`.

## Roadmap (next milestones)

1. ~~Richer LLM metrics (TTFT/TPOT, tokens, error classes)~~ **Done**
2. Backend abstraction + path to vLLM
3. Published benchmarks with controlled runs (optional GPU cloud)
4. Evaluation / feedback harness attached to the gateway

## License

See [LICENSE](LICENSE).
