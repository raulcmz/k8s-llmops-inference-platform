# Gateway eval harness (Hito 5)

Offline evaluation of the inference gateway: versioned cases → call `/chat` → automatic checks → JSON report.

This is **quality** evaluation (did the answer satisfy expectations?), not serving benchmarks (TTFT/TPOT). Those live under the gateway `/metrics`.

## Layout

```text
evals/
  cases/           # JSONL suites (one case per line)
  harness/         # case schema, checks, gateway client, reports
  reports/         # generated run reports (gitignored)
  run_eval.py      # CLI entrypoint
  tests/           # unit tests for checks/loader (no live gateway required)
```

## Case format (JSONL)

Each line is one JSON object:

```json
{
  "id": "smoke-greeting-es",
  "prompt": "Responde solo con una frase corta en español saludando.",
  "model": null,
  "expect": {
    "contains_any": ["Hola", "hola"],
    "contains_all": [],
    "min_chars": 3,
    "max_chars": null
  }
}
```

| Field | Meaning |
|---|---|
| `id` | Stable case id (used in reports) |
| `prompt` | Sent to gateway `/chat` |
| `model` | Optional; omit/`null` → gateway default |
| `expect.contains_any` | Pass if **any** substring is present |
| `expect.contains_all` | Pass if **all** substrings are present |
| `expect.min_chars` / `max_chars` | Optional length bounds |

These checks are **heuristic**. They are not a full measure of answer quality. Human rubrics and stronger judges come in later H5 tasks.

## Run against a live gateway

Terminal A — gateway (example Ollama lab):

```bash
cd apps/gateway
source .venv/bin/activate
export OLLAMA_BASE_URL=http://192.168.1.131:11434
export DEFAULT_MODEL=mistral:7b
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Terminal B — evals:

```bash
cd evals
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export GATEWAY_URL=http://127.0.0.1:8080
python run_eval.py --suite smoke
```

Exit code `0` if all cases passed; `1` if any failed; `2` if suite missing.

Reports are written under `evals/reports/`.

## Unit tests (no gateway)

From repo root:

```bash
cd evals
pip install -r requirements.txt pytest
PYTHONPATH=.. pytest -v
```

## Next (same hito)

- Richer scorers / structured JSON validation
- Human feedback (rubrics / pairwise preferences)
- Baseline vs candidate promotion gate
