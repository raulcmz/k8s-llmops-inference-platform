# K8s LLMOps Inference Platform

Lab project: an **internal LLM inference gateway** on Kubernetes that fronts a remote model server (**Ollama** today; **vLLM** via adapter when available).

This is a **foundation for LLMOps experimentation**, not a full production LLM platform. The focus is platform engineering patterns around LLM serving: stable API edge, health semantics, config-as-env, pluggable inference backends, tests, CI, and K8s probes.

## What it is (today)

```text
Client (curl / other services)
        ↓
Internal LLM Gateway (FastAPI :8080)
  /health       → liveness (process only)
  /ready        → readiness (configured backend reachable)
  /models       → list models from backend
  /chat         → non-streaming generate (JSON)
  /chat/stream  → streaming generate (NDJSON to the client)
  /metrics      → Prometheus metrics
        ↓
   LLMBackend protocol
      ↙        ↘
 OllamaBackend   VllmBackend
 (NDJSON native) (OpenAI API + SSE → translated)
      ↓              ↓
 Ollama :11434    vLLM :8000 (optional / GPU)
```

### Included

| Area | Status |
|---|---|
| FastAPI gateway | Done |
| Split `/health` vs `/ready` | Done |
| Config via env (`pydantic-settings`) | Done |
| `LLMBackend` protocol + Ollama adapter | Done |
| vLLM OpenAI-compatible adapter (SSE→NDJSON) | Done |
| Non-stream `/chat` + stream `/chat/stream` (NDJSON) | Done |
| Prometheus metrics (E2E, tokens, errors, TTFT/TPOT) | Done |
| Unit tests with mocked backends (`pytest` + `respx`) | Done |
| GitHub Actions CI on gateway changes | Done |
| Quality eval harness (`evals/`) | Done |
| Human feedback (rubric + pairwise) | Done |
| Baseline vs candidate promotion gate | Done |
| GitHub Actions CI on evals unit tests | Done |
| K8s Deployment probes + ConfigMap | Done |
| Ollama via manual Service/Endpoints (lab) | Done |

### Explicitly not included yet

- Live vLLM Deployment manifests / GPU runbooks (adapter is ready; GPU optional)
- Auth, rate limiting, TLS
- Autoscaling / HA beyond a single replica demo
- MLflow / MinIO benchmark artifact store
- Published benchmark tables with controlled GPU runs

## Repository layout

```text
apps/gateway/app/backends/   # LLMBackend protocol + Ollama/vLLM adapters
apps/gateway/               # FastAPI app, Dockerfile, tests, requirements
evals/                      # Quality evals: cases, checks, human feedback, promote gate
benchmarks/                 # Serving latency benches (TTFT/TPOT/E2E via /chat/stream)
k8s/gateway/                # Deployment, Service, ConfigMap, ServiceMonitor
k8s/ollama-backend/         # Lab Service + Endpoints → Windows host IP
.github/workflows/          # CI (gateway + evals + benchmarks unit tests)
```

## Inference backends (Ollama vs vLLM)

Both are **LLM inference engines** (load a model, generate tokens). The gateway talks to them through adapters so `/chat` stays stable.

| | Ollama | vLLM |
|---|---|---|
| Role | Easy local/lab runtime | High-throughput GPU serving |
| Typical DX | Very high (`ollama run …`) | Lower (CUDA, serve flags) |
| Native stream wire format | **NDJSON** | **SSE** (`data: …`, `data: [DONE]`) |
| HTTP style | Ollama API (`/api/generate`, `/api/tags`) | OpenAI-compatible (`/v1/chat/completions`, `/v1/models`) |
| Default port (convention) | `11434` | `8000` |
| Select in gateway | `BACKEND_TYPE=ollama` | `BACKEND_TYPE=vllm` |
| Base URL env | `OLLAMA_BASE_URL` | `VLLM_BASE_URL` |

**DX** = *Developer Experience* (how easy it is for a developer to install, run, and iterate).

Other engines (e.g. TensorRT-LLM on NVIDIA stacks) could become additional adapters behind the same `LLMBackend` protocol.

### NDJSON vs SSE (why the vLLM adapter exists)

| | NDJSON | SSE (Server-Sent Events) |
|---|---|---|
| Shape | one JSON object per line | lines prefixed with `data: ` |
| Content-Type | `application/x-ndjson` | `text/event-stream` |
| Gateway **client** API (`/chat/stream`) | Yes | No |
| Ollama stream | Yes | No |
| vLLM OpenAI stream | No | Yes |

The **vLLM adapter** reads SSE from the engine and emits the gateway’s NDJSON event shape (`response` / `done` / token fields). That keeps TTFT/TPOT logic and client curls unchanged.

## Quick start (no Kubernetes) — Ollama lab

Typical lab: **Ollama on Windows**, gateway on an **Ubuntu VM**.

```bash
cd apps/gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export BACKEND_TYPE=ollama
export OLLAMA_BASE_URL=http://<WINDOWS_HOST_IP>:11434   # e.g. 192.168.1.131
export DEFAULT_MODEL=mistral:7b

uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Smoke checks:

```bash
curl -s http://127.0.0.1:8080/health
curl -s -i http://127.0.0.1:8080/ready
curl -s http://127.0.0.1:8080/models

curl -s http://127.0.0.1:8080/chat \
  -H 'content-type: application/json' \
  -d '{"prompt":"hola en una frase"}'

# Stream (NDJSON; -N disables curl buffering)
curl -N http://127.0.0.1:8080/chat/stream \
  -H 'content-type: application/json' \
  -d '{"prompt":"hola en una frase"}'

curl -s http://127.0.0.1:8080/metrics | rg 'llm_'
```

Expected:

- `/health` → `200` if the process is up
- `/ready` → `200` if the configured backend answers; `503` if not
- `/ready` JSON includes `backend` (`ollama` or `vllm`) and `backend_url`
- `/chat/stream` prints one JSON object per line until `"done": true`

### Optional: point at vLLM (when you have a server)

```bash
export BACKEND_TYPE=vllm
export VLLM_BASE_URL=http://<VLLM_HOST>:8000
# examples:
#   same VM:     http://127.0.0.1:8000
#   Windows lab: http://192.168.1.131:8000
#   Kubernetes:  http://vllm:8000
```

`8000` is vLLM’s usual default listen port (convention, not a hard rule). Verify with:

```bash
curl -s "$VLLM_BASE_URL/v1/models"
```

You do **not** need vLLM for day-to-day lab work on this repo; tests mock it.

## Metrics (Prometheus `/metrics`)

All series are exposed by the gateway. Labels commonly include `model` and, where relevant, `mode=non_stream|stream`.

| Metric | What it measures | When it is recorded |
|---|---|---|
| `llm_requests_total` | Chat requests received | `/chat` and `/chat/stream` |
| `llm_errors_total{error_type=...}` | `connect`, `timeout`, `backend_http` | Failed chat attempts |
| `llm_request_duration_seconds` | **End-to-end** latency of non-stream `/chat` | `/chat` only |
| `llm_prompt_tokens_total` / `llm_completion_tokens_total` | Tokens reported by the engine (normalized) | When the adapter provides counts |
| `llm_backend_prompt_eval_seconds` | Engine prompt-eval duration (Ollama field when present) | When present |
| `llm_backend_eval_seconds` | Engine generation duration (Ollama field when present) | When present |
| `llm_backend_total_seconds` | Engine total duration (Ollama field when present) | When present |
| `llm_ttft_seconds` | **Time to first token** | `/chat/stream` only |
| `llm_tpot_seconds` | Avg time per output token after the first | `/chat/stream` only (`n>=2`) |

### Honest naming notes

- **E2E ≠ TTFT.** `llm_request_duration_seconds` is full request time for non-stream `/chat`.
- **TTFT/TPOT require streaming** on `/chat/stream` (works for Ollama native NDJSON and for vLLM after SSE→NDJSON translation).
- Lab CPU + Ollama often shows high TTFT (seconds) and modest TPOT; expected without a dedicated GPU.

### Example lab observation (CPU, Ollama `mistral:7b`)

- TTFT ≈ 9.6s
- TPOT ≈ 0.14s/token

## Tests & CI

Gateway (mocked backends — no GPU required):

```bash
cd apps/gateway
pip install -r requirements-dev.txt
python -m pytest -v
```

Quality evals (harness / feedback / gate — no live model required):

```bash
cd evals
# prefer: uv venv .venv-evals && source .venv-evals/bin/activate
pip install -r requirements.txt pytest
PYTHONPATH=.. pytest -v
```

CI: gateway job on `apps/gateway/**`; evals job on `evals/**`.

## Quality evals (offline demo)

Serving metrics (TTFT/TPOT) live under `/metrics`. **Quality** evals live under [`evals/`](evals/): versioned cases → automatic checks → optional human rubric/pairwise → baseline vs candidate **promotion gate**.

Clone-and-run (no Ollama):

```bash
cd evals
uv venv .venv-evals && source .venv-evals/bin/activate
uv pip install -r requirements.txt pytest
PYTHONPATH=.. pytest -v

python promote_gate.py \
  --baseline gates/fixtures/baseline_smoke.json \
  --candidate gates/fixtures/candidate_smoke_promote.json   # exit 0

python promote_gate.py \
  --baseline gates/fixtures/baseline_smoke.json \
  --candidate gates/fixtures/candidate_smoke_block.json     # exit 1
```

Generated reports under `evals/reports/` are gitignored (regenerable lab artifacts). See [`evals/README.md`](evals/README.md) for the full lab demo loop (live gateway optional).

## Kubernetes (lab)

See [`k8s/README.md`](k8s/README.md) for apply order.

Important lab caveats:

1. `k8s/ollama-backend/endpoints.yaml` points at a **host IP** (currently `192.168.1.131`). Update on DHCP changes.
2. For local runs, set `OLLAMA_BASE_URL` to the Windows host IP; default `http://ollama:11434` is for in-cluster DNS.
3. Gateway image tag in Deployment may lag `main`; rebuild/push before relying on new features in-cluster.
4. Optional `ServiceMonitor` needs Prometheus Operator.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `BACKEND_TYPE` | `ollama` | Adapter: `ollama` or `vllm` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | When `BACKEND_TYPE=ollama` |
| `VLLM_BASE_URL` | `http://vllm:8000` | When `BACKEND_TYPE=vllm` |
| `DEFAULT_MODEL` | `mistral:7b` | Model when request omits `model` |
| `READY_CHECK_TIMEOUT_SECONDS` | `2` | Readiness probe budget |
| `MODELS_TIMEOUT_SECONDS` | `10` | `/models` timeout |
| `CHAT_TIMEOUT_SECONDS` | `120` | `/chat` and `/chat/stream` timeout |

## Roadmap (next milestones)

1. ~~Richer LLM metrics (TTFT/TPOT, tokens, error classes)~~ **Done**
2. ~~Backend abstraction + path to vLLM~~ **Done**
3. ~~Evaluation / human-feedback / promotion gate~~ **Done** ([`evals/`](evals/))
4. Published benchmarks with controlled runs (optional GPU cloud) — **in progress** ([`benchmarks/`](benchmarks/))

## License

See [LICENSE](LICENSE).
