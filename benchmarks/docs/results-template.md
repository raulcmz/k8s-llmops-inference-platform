# Benchmark results template

Copy this file (e.g. to `benchmarks/results/YYYYMMDD-short-title.md`) and fill it.  
Leave unknown fields as `not_run` or `n/a` — never invent values.

See [`metrics.md`](metrics.md) for plain-language definitions of every field.

---

## 1. Run identity

| Field | Value |
|---|---|
| Title | |
| Date (UTC) | |
| Operator | |
| Git commit | |
| Branch | |
| Command(s) run | |
| Report JSON path (local) | |
| Report Markdown path (local) | |

## 2. Environment metadata

| Field | Value |
|---|---|
| hardware | |
| CPU / RAM notes | |
| GPU model (if any) | |
| GPU VRAM (if any) | |
| backend (`ollama` / `vllm`) | |
| backend URL | |
| model | |
| gateway URL | |
| cold_or_warm | |
| concurrency levels tested | |
| requests_per_level | |
| case_id / suite | |
| cost note (cloud $/h, if any) | |
| extra notes | |

## 3. Client bench — sequential suite (optional)

Fill if you ran Mode A (`run_bench.py` without `--concurrency`).

### 3.1 Aggregate summary

| Metric | Value |
|---|---|
| requests (total) | |
| ok | |
| failed | |
| TTFT p50 (s) | |
| TTFT p95 (s) | |
| TTFT mean (s) | |
| TTFT min (s) | |
| TTFT max (s) | |
| TPOT p50 (s/token) | |
| TPOT p95 (s/token) | |
| TPOT mean (s/token) | |
| E2E p50 (s) | |
| E2E p95 (s) | |
| E2E mean (s) | |
| E2E min (s) | |
| E2E max (s) | |

### 3.2 Per-case samples (optional detail)

| case_id | ok | TTFT (s) | TPOT (s) | E2E (s) | prompt_tokens | completion_tokens |
|---|---|---|---|---|---|---|
| | | | | | | |
| | | | | | | |
| | | | | | | |

## 4. Client bench — concurrency sweep (Mode B)

One row per concurrency level.

| concurrency | ok/total | TTFT p50 | TTFT p95 | TPOT p50 | TPOT p95 | E2E p50 | E2E p95 | wall_s | req/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | | | | | | | | | |
| 2 | | | | | | | | | |
| 4 | | | | | | | | | |

### 4.1 What changed when concurrency went up? (your words)

- TTFT p95:
- req/s:
- Any failures / timeouts:

## 5. Gateway Prometheus snapshot (optional but recommended)

**You on the VM** can capture after the bench:

```bash
curl -sS http://127.0.0.1:8080/metrics | rg 'llm_'
```

Record either histogram summaries you care about or a short note (“scraped, see local file”).

| Series | What you observed / note |
|---|---|
| `llm_requests_total` | |
| `llm_errors_total` | |
| `llm_ttft_seconds` | |
| `llm_tpot_seconds` | |
| `llm_request_duration_seconds` | |
| `llm_prompt_tokens_total` | |
| `llm_completion_tokens_total` | |
| `llm_backend_prompt_eval_seconds` | |
| `llm_backend_eval_seconds` | |
| `llm_backend_total_seconds` | |

## 6. Honesty / limits

- [ ] Metadata filled
- [ ] Hardware labeled (cpu vs gpu)
- [ ] No invented numbers
- [ ] Cloud GPU stopped (if used)
- [ ] This is quality-neutral (speed only; quality is `evals/`)

## 7. Conclusion (2–4 sentences)

…
