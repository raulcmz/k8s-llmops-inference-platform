# Metrics glossary (plain language)

This page lists **every important metric** used in this lab for serving speed.

Two places measure time:

1. **Client bench** (`benchmarks/run_bench.py`) — stopwatch on the machine that *sends* the chat.
2. **Gateway Prometheus** (`GET /metrics`) — stopwatch *inside* the gateway process.

They should be close, but not identical (network, buffering). Always say which one you quote.

---

## A. Client bench metrics (`run_bench.py` reports)

These appear in JSON under `summary` / `levels[].summary` and in Markdown tables.

### Latency (how long you wait)

| Metric | Full name | Plain meaning | When it matters |
|---|---|---|---|
| **TTFT** | Time To First Token | Wait until the **first** piece of the answer appears | Chat UX: “is it thinking forever?” |
| **TPOT** | Time Per Output Token | Average wait **per token** after the first | How fast the answer “types” |
| **E2E** | End-to-End latency | From send prompt → full answer finished | Total patience required for one reply |

For each of TTFT / TPOT / E2E the report stores:

| Field | Plain meaning |
|---|---|
| `count` | How many successful samples entered the math |
| `min` | Fastest run |
| `max` | Slowest run |
| `mean` | Average |
| **`p50`** | Typical run (median): half faster, half slower |
| **`p95`** | Slow tail: ~95% of runs were faster than this |

**Rule of thumb:** quote **p50** for “normal day”, **p95** for “what annoyed users felt”.

### Load / capacity

| Metric | Plain meaning |
|---|---|
| **concurrency** | How many chats we kept open **at the same time** |
| **requests** | How many chats we attempted at that level |
| **ok** / **failed** | How many succeeded vs failed |
| **wall_seconds** | Clock time to finish the **whole batch** at that concurrency |
| **requests_per_second** (`req/s`) | Successful finishes ÷ wall time (batch throughput) |

### Per-sample fields (each row in `samples`)

| Field | Plain meaning |
|---|---|
| `case_id` | Which prompt / label |
| `ok` | Finished without client/gateway error |
| `error` | Error text if any |
| `ttft_seconds` / `tpot_seconds` / `e2e_seconds` | That single run’s times |
| `prompt_tokens` | Tokens in the question (if backend reported) |
| `completion_tokens` | Tokens in the answer (if backend reported) |
| `chunks_with_text` | How many stream chunks carried text |
| `response_preview` | Short peek at the text (for debugging, not quality scoring) |

### Metadata (not a speed metric — but mandatory)

Put these next to every published number:

| Field | Example | Why |
|---|---|---|
| `hardware` | `cpu-lab` / `vast-rtx3090` | CPU ≠ GPU |
| `backend` | `ollama` / `vllm` | Engine changes latency a lot |
| `model` | `mistral:7b` | Different models → different speed |
| `git_commit` | `68b83b1` | So you know which code |
| `cold_or_warm` | `cold` / `warm` | First load vs already hot |
| `date_utc` | ISO timestamp | When it was measured |
| `notes` | free text | Anything weird (VPN, shared host, …) |

---

## B. Gateway Prometheus metrics (`/metrics`)

Scraped from the gateway. Names are exact series labels.

### Traffic and errors

| Series | Plain meaning |
|---|---|
| `llm_requests_total` | How many chat requests the gateway received (`model`, `mode=non_stream\|stream`) |
| `llm_errors_total` | How many failed, by `error_type` (`connect`, `timeout`, `backend_http`, …) and `mode` |

### Latency (gateway-measured)

| Series | Plain meaning | Endpoint |
|---|---|---|
| `llm_request_duration_seconds` | **E2E** for non-stream `/chat` only (not TTFT) | `/chat` |
| `llm_ttft_seconds` | **TTFT** until first non-empty stream chunk | `/chat/stream` |
| `llm_tpot_seconds` | **TPOT** after first token (needs ≥2 completion tokens) | `/chat/stream` |

### Tokens

| Series | Plain meaning |
|---|---|
| `llm_prompt_tokens_total` | Prompt tokens reported by backend |
| `llm_completion_tokens_total` | Answer tokens reported by backend |

### Backend-reported timings (often Ollama fields)

These are what the **engine** claims, not the client stopwatch.

| Series | Plain meaning |
|---|---|
| `llm_backend_prompt_eval_seconds` | Time the engine spent on the prompt (“reading the question”) |
| `llm_backend_eval_seconds` | Time the engine spent generating tokens |
| `llm_backend_total_seconds` | Engine total duration field when present |

---

## C. What we do **not** treat as serving metrics here

| Topic | Where it lives |
|---|---|
| “Was the answer correct / good?” | `evals/` (quality checks, rubrics, pairwise) |
| Promotion gate pass/fail | `evals/promote_gate.py` |
| Fake GPU numbers without a real run | Forbidden — leave blank or mark `not_run` |

---

## D. Quick “which number should I publish?” cheat sheet

| Story you want to tell | Publish at least |
|---|---|
| “First word feels snappy” | TTFT p50 + p95 + concurrency + metadata |
| “Typing speed of the answer” | TPOT p50 (+ p95 if you have it) |
| “Whole reply patience” | E2E p50 + p95 |
| “Holds up with several users” | Table vs concurrency: TTFT p95 + req/s + wall_s |
| “System health in ops” | Prometheus error rate + gateway TTFT histogram |

Always include: **hardware, backend, model, commit, cold/warm, date**.
