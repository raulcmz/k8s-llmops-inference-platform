# K8s LLMOps Inference Platform

Lab project: an **internal LLM inference gateway** on Kubernetes that fronts a remote model server (today: **Ollama** outside the cluster).

This is a **foundation for LLMOps experimentation**, not a full production LLM platform. The focus is platform engineering patterns around LLM serving: stable API edge, health semantics, config-as-env, tests, CI, and K8s probes.

## What it is (today)

```text
Client (curl / other services)
        ↓
Internal LLM Gateway (FastAPI :8080)
  /health  → liveness (process only)
  /ready   → readiness (backend reachable)
  /models  → proxy to Ollama tags
  /chat    → proxy to Ollama generate
  /metrics → Prometheus metrics
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
| Prometheus `/metrics` + ServiceMonitor manifest | Done (metrics basic) |
| Unit tests with mocked backend (`pytest` + `respx`) | Done |
| GitHub Actions CI on gateway changes | Done |
| K8s Deployment probes + ConfigMap | Done |
| Ollama via manual Service/Endpoints (lab) | Done |

### Explicitly not included yet

- vLLM / multi-backend routing
- Auth, rate limiting, TLS
- Autoscaling / HA beyond a single replica demo
- Real TTFT/TPOT / token-level metrics
- Evaluation / human-feedback loop
- MLflow / MinIO benchmark artifact store

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
curl -s http://127.0.0.1:8080/chat \
  -H 'content-type: application/json' \
  -d '{"prompt":"hola en una frase"}'
```

Expected:

- `/health` → `200` if the process is up
- `/ready` → `200` if Ollama answers; `503` if not
- Stopping Ollama should flip `/ready` to `503` without killing `/health`

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

1. `k8s/ollama-backend/endpoints.yaml` points at a **host IP** (VMware/Windows). Update it when the IP changes. This is not a production service-discovery pattern.
2. `Deployment` image `rcabe005/llm-gateway:0.1.1` must include `/ready`. Rebuild/push from current `main` if probes return 404.
3. Optional `ServiceMonitor` only works if Prometheus Operator is installed.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Backend base URL |
| `DEFAULT_MODEL` | `mistral:7b` | Model when `/chat` omits `model` |
| `READY_CHECK_TIMEOUT_SECONDS` | `2` | Readiness probe budget |
| `MODELS_TIMEOUT_SECONDS` | `10` | `/models` timeout |
| `CHAT_TIMEOUT_SECONDS` | `120` | `/chat` timeout |

In cluster, these are provided by `k8s/gateway/configmap.yaml`.

## Roadmap (next milestones)

1. Richer LLM metrics (TTFT/TPOT, tokens, error classes)
2. Backend abstraction + path to vLLM
3. Published benchmarks with real numbers in this README
4. Evaluation / feedback harness attached to the gateway

## License

See [LICENSE](LICENSE).
