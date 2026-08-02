# Serving benchmarks (Hito 4)

Measure **serving latency** against the inference gateway (`/chat/stream`):

- **TTFT** (*Time To First Token*) — client time until the first non-empty `response` chunk
- **TPOT** (*Time Per Output Token*) — client estimate after the first token
- **E2E** (*End-to-End*) — full stream wall time

This is **not** quality evaluation (`evals/`). Soft/hard answer checks live there.

## Lab demo (H4-T1)

### Unit tests (no gateway)

```bash
cd benchmarks
uv venv .venv-bench
source .venv-bench/bin/activate
uv pip install -r requirements.txt
uv pip install pytest respx
PYTHONPATH=.. pytest -v
```

### Live smoke (gateway + Ollama lab)

```bash
# Terminal A: apps/gateway with OLLAMA_BASE_URL / DEFAULT_MODEL
# Terminal B:
cd benchmarks
source .venv-bench/bin/activate
export GATEWAY_URL=http://127.0.0.1:8080
python run_bench.py --suite smoke_latency \
  --metadata '{"hardware":"cpu-lab","backend":"ollama","model":"mistral:7b"}'
```

Reports under `reports/` are **gitignored** (same rationale as `evals/reports/`).

Optional: compare client TTFT with Prometheus `llm_ttft_seconds` on the gateway `/metrics`.

## Layout

```text
benchmarks/
  cases/           # JSONL prompt suites
  harness/         # loader, stream client, stats, report
  reports/         # generated JSON (gitignored)
  run_bench.py
  tests/
  .venv-bench/     # local uv venv (gitignored)
```

## Next (same hito)

- Concurrency sweeps (1/2/4)
- Controlled-run metadata / publishable markdown tables
- Optional Vast.ai + vLLM run (cost-aware; screenshots/docs when configured)
