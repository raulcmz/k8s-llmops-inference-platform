# Serving benchmarks (Hito 4)

This folder answers a simple question:

> **When someone chats with our gateway, how long do they wait?**

It does **not** judge if the answer is smart or correct. That is `evals/` (quality).  
Here we only measure **speed**.

## Words you will see (plain language)

| Word | Meaning in this lab |
|---|---|
| **Gateway** | Small web service (`:8080`) that sits in front of the model |
| **Streaming** | The answer arrives word-by-word (chunks), not all at once |
| **TTFT** | *Time To First Token* — wait until the **first** bit of answer appears |
| **TPOT** | *Time Per Output Token* — average wait **per word/token** after the first |
| **E2E** | *End-to-End* — time from “send question” until “answer fully done” |
| **Concurrency** | How many chats we keep open **at the same time** |
| **p50** | “Typical” value (half of the runs were faster, half slower) |
| **p95** | “Slow tail” (about 95% were faster than this; the annoying waits) |
| **req/s** | How many successful answers we finished **per second** in a batch |

Analogy: a café.

- **TTFT** = time until the first sip  
- **E2E** = time until you finish the drink  
- **Concurrency** = how many customers the barista tries to serve together  
- **p95** = the unlucky customer who waited the longest (almost)

## Setup (once)

```bash
cd benchmarks
uv venv .venv-bench
source .venv-bench/bin/activate          # Windows: .venv-bench\Scripts\activate
uv pip install -r requirements.txt
uv pip install pytest respx              # for unit tests
```

## Mode A — Simple (one after another)

Good first check. Three short prompts, one at a time.

```bash
export GATEWAY_URL=http://127.0.0.1:8080
python run_bench.py --suite smoke_latency \
  --metadata '{"hardware":"cpu-lab","backend":"ollama","model":"mistral:7b"}'
```

## Mode B — Concurrency sweep (H4-T2)

We repeat **one** prompt while increasing “how many at once”: 1, then 2, then 4.

Why one prompt? So the only thing that changes is load, not the question text.

```bash
python run_bench.py --suite smoke_latency \
  --case-id bench-short-es \
  --concurrency 1,2,4 \
  --requests-per-level 3 \
  --write-markdown \
  --metadata '{"hardware":"cpu-lab","backend":"ollama","model":"mistral:7b"}'
```

What you get:

1. JSON report under `reports/` (machine-readable, **not** committed to git)
2. Markdown table `.md` next to it (easy to read / paste into notes)

On a **CPU** lab, higher concurrency often makes **TTFT p95 worse** (queue).  
That is normal and useful: the table shows the pain.

## Unit tests (no model needed)

```bash
PYTHONPATH=.. pytest -v
```

## Layout

```text
benchmarks/
  cases/           # list of prompts (JSONL = one JSON object per line)
  harness/         # code that calls the gateway and does the math
  reports/         # your run outputs (gitignored)
  run_bench.py     # command you run
  tests/           # automatic tests for the math/helpers
  .venv-bench/     # private Python environment for this folder
```

## Next (same hito)

- Controlled-run checklist / publishable notes template
- Optional Vast.ai + vLLM run (paid GPU; screenshots when access is configured)
