# Serving benchmarks (Hito 4)

This folder answers a simple question:

> **When someone chats with our gateway, how long do they wait?**

It does **not** judge if the answer is smart or correct. That is `evals/` (quality).  
Here we only measure **speed**.

## Docs (metrics & process)

| Doc | What it is |
|---|---|
| [`docs/metrics.md`](docs/metrics.md) | **All important metrics** (client bench + Prometheus) in plain language |
| [`docs/controlled-run-checklist.md`](docs/controlled-run-checklist.md) | Before / during / after checklist so numbers are trustworthy |
| [`docs/results-template.md`](docs/results-template.md) | Empty form to record a real run (every metric field listed) |

## Words you will see (short list)

| Word | Meaning in this lab |
|---|---|
| **Gateway** | Small web service (`:8080`) that sits in front of the model |
| **Streaming** | The answer arrives word-by-word (chunks), not all at once |
| **TTFT** | *Time To First Token* — wait until the **first** bit of answer appears |
| **TPOT** | *Time Per Output Token* — average wait **per token** after the first |
| **E2E** | *End-to-End* — time from “send question” until “answer fully done” |
| **Concurrency** | How many chats we keep open **at the same time** |
| **p50** | Typical value (half of runs faster, half slower) |
| **p95** | Slow tail (~95% of runs were faster than this) |
| **req/s** | Successful answers finished **per second** in a batch |

Full tables (including Prometheus series names): [`docs/metrics.md`](docs/metrics.md).

Analogy: a café — TTFT = first sip; E2E = finish the drink; concurrency = customers at once; p95 ≈ the unlucky long wait.

## Setup (once)

```bash
cd benchmarks
uv venv .venv-bench
source .venv-bench/bin/activate          # Windows: .venv-bench\Scripts\activate
uv pip install -r requirements.txt
uv pip install pytest respx              # for unit tests
```

## Mode A — Simple (one after another)

Requires a running gateway.

```bash
export GATEWAY_URL=http://127.0.0.1:8080
python run_bench.py --suite smoke_latency \
  --metadata '{"hardware":"cpu-lab","backend":"ollama","model":"mistral:7b"}'
```

## Mode B — Concurrency sweep

```bash
python run_bench.py --suite smoke_latency \
  --case-id bench-short-es \
  --concurrency 1,2,4 \
  --requests-per-level 3 \
  --write-markdown \
  --metadata '{"hardware":"cpu-lab","backend":"ollama","model":"mistral:7b"}'
```

Outputs (local, gitignored under `reports/`):

1. JSON report  
2. Markdown table (with `--write-markdown`)

Record curated numbers with [`docs/results-template.md`](docs/results-template.md) (from the report + optional `/metrics`).

## Unit tests (no model needed)

```bash
PYTHONPATH=.. pytest -v
```

CI runs these on changes under `benchmarks/**`.

## Layout

```text
benchmarks/
  cases/           # prompts (JSONL)
  harness/         # client + stats + concurrency
  docs/            # metrics glossary, checklist, results template
  results/         # optional curated notes (commit only when intentional)
  reports/         # raw run outputs (gitignored)
  run_bench.py
  tests/
  .venv-bench/
```

## Next (same hito)

- Optional Vast.ai + vLLM controlled run (paid GPU)
