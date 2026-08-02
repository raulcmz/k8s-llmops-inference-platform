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
  .venv-evals/     # local uv venv for this package (gitignored; create yourself)
```

The venv is named **`.venv-evals`** (not `.venv`) so it is easy to tell apart from `apps/gateway/.venv` when both are active in the lab.

## Case format (JSONL)

Each line is one JSON object:

```json
{
  "id": "smoke-json-keys",
  "prompt": "Devuelve ÚNICAMENTE un JSON válido ...",
  "model": null,
  "expect": {
    "json_valid": true,
    "json_object": true,
    "json_required_keys": ["name", "city"],
    "json_equals": {"name": "Ana", "city": "Madrid"},
    "max_chars": 120
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
| `expect.json_valid` | Require JSON parse success (`true`) or failure (`false`) |
| `expect.json_object` | Require parsed value to be a JSON object (`dict`) |
| `expect.json_required_keys` | Top-level keys that must exist |
| `expect.json_equals` | **Total** equality against the expected object |

JSON checks accept a fenced markdown code block (`json` language tag optional) when the model wraps the payload; the check detail records `fence` vs `raw`.

Heuristic substring checks are still useful for smoke prompts. Structural JSON checks are stronger for “API contract” style cases. Human rubrics come in a later H5 task.

## Setup with uv

Install [uv](https://docs.astral.sh/uv/) once on the machine, then from repo:

```bash
cd evals

# If you still have the old generic name, replace it:
# rm -rf .venv

uv venv .venv-evals
source .venv-evals/bin/activate          # Windows: .venv-evals\Scripts\activate
uv pip install -r requirements.txt
uv pip install pytest                    # only needed for unit tests
```

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
source .venv-evals/bin/activate
export GATEWAY_URL=http://127.0.0.1:8080
python run_eval.py --suite smoke
```

Exit code `0` if all cases passed; `1` if any failed; `2` if suite missing.

On failure the CLI prints each check (`name`, ok/FAIL, detail). The JSON report under `evals/reports/` includes `summary.failed_by_check`.

## Unit tests (no gateway)

From `evals/` with `.venv-evals` active:

```bash
PYTHONPATH=.. pytest -v
```

Or from repo root:

```bash
cd evals && source .venv-evals/bin/activate
PYTHONPATH=.. pytest -v
```

## Next (same hito)

- Human feedback (rubrics / pairwise preferences)
- Baseline vs candidate promotion gate
