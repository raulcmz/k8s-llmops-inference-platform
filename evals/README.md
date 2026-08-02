# Gateway eval harness (Hito 5)

Offline **quality** evaluation of the inference gateway:

```text
versioned cases → /chat → automatic checks → JSON report
                 → optional human feedback (rubric / pairwise)
                 → baseline vs candidate promotion gate
```

This is not serving benchmarks (TTFT/TPOT). Those live under the gateway `/metrics`.

## Lab demo loop

Two paths. Prefer **A** when cloning the repo; use **B** in the Ollama lab.

### A — Offline (no gateway, no model)

```bash
cd evals
uv venv .venv-evals
source .venv-evals/bin/activate          # Windows: .venv-evals\Scripts\activate
uv pip install -r requirements.txt
uv pip install pytest

PYTHONPATH=.. pytest -v

# Promotion gate dry-run (committed fixtures)
python promote_gate.py \
  --policy gates/smoke_promote_v1.json \
  --baseline gates/fixtures/baseline_smoke.json \
  --candidate gates/fixtures/candidate_smoke_promote.json
echo "promote_exit=$?"   # expect 0

python promote_gate.py \
  --policy gates/smoke_promote_v1.json \
  --baseline gates/fixtures/baseline_smoke.json \
  --candidate gates/fixtures/candidate_smoke_block.json
echo "block_exit=$?"     # expect 1

# Human-feedback summary from committed examples
python annotate.py summarize
```

### B — Live lab (gateway + Ollama)

Terminal A — gateway:

```bash
cd apps/gateway
source .venv/bin/activate
export OLLAMA_BASE_URL=http://192.168.1.131:11434   # your Windows host IP
export DEFAULT_MODEL=mistral:7b
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Terminal B — evals:

```bash
cd evals
source .venv-evals/bin/activate
export GATEWAY_URL=http://127.0.0.1:8080

curl -sS "$GATEWAY_URL/health"; echo
curl -sS "$GATEWAY_URL/ready"; echo

python run_eval.py --suite smoke
# CPU models may fail soft cases (e.g. smoke-refusal-length); that is useful signal.

# Optional: score a failed/interesting case
python annotate.py rubric \
  --report reports/smoke_XXXX.json \
  --case-id smoke-refusal-length \
  --rater-id raul \
  --scores '{"instruction_following":1,"clarity":4,"concision":2,"safety_basic":5}'

# Optional: compare two saved runs
python promote_gate.py \
  --baseline reports/smoke_baseline.json \
  --candidate reports/smoke_candidate.json
```

### Artifacts: what is (not) in git

| In git | Not in git (local / CI artifacts) |
|---|---|
| Cases, rubrics, gate policy, fixtures | `reports/*.json` from live runs |
| Feedback **examples** | `feedback/rubric/` and `feedback/pairwise/` annotations |
| Harness code + unit tests | Gate decision JSON under `reports/gates/` |

Reports are regenerable lab outputs (timestamps, model text, host URLs). Version the **policy and fixtures**, not every run.

## Layout

```text
evals/
  cases/           # JSONL suites (one case per line)
  harness/         # case schema, checks, gateway client, reports, feedback, gate
  rubrics/         # versioned human rubrics (criteria + behavioral anchors)
  feedback/        # human annotations (rubric/ + pairwise/; examples/ committed)
  gates/           # promotion policies + fixtures (baseline/candidate samples)
  reports/         # generated run reports (gitignored)
  reports/gates/   # gate decision JSON (gitignored)
  run_eval.py      # automatic eval CLI
  annotate.py      # human feedback CLI
  promote_gate.py  # baseline vs candidate promotion gate
  tests/           # unit tests (no live gateway required)
  .venv-evals/     # local uv venv for this package (gitignored; create yourself)
```

The venv is named **`.venv-evals`** (not `.venv`) so it is easy to tell apart from `apps/gateway/.venv`.

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

`run_eval.py` exit codes: `0` all passed, `1` any failed, `2` suite missing.  
On failure the CLI prints each check; reports include `summary.failed_by_check`.

## Human feedback (rubrics / pairwise)

Automatic checks do not measure “was this answer good?”. Human feedback fills that gap with:

1. **Rubric scores** (1–5) against versioned criteria with behavioral anchors — see `rubrics/response_quality_v1.json`.
2. **Pairwise preference** (A / B / tie) with randomized on-screen order (`order_presented` is stored to document position bias controls).

```bash
python annotate.py rubric \
  --report reports/smoke_XXXX.json \
  --case-id smoke-refusal-length \
  --rater-id raul \
  --scores '{"instruction_following":1,"clarity":4,"concision":2,"safety_basic":5}' \
  --notes "Model ignored solo OK"

python annotate.py pairwise \
  --prompt "Di solo la palabra OK." \
  --a "OK" \
  --b "Por supuesto, aquí tienes la confirmación..." \
  --rater-id raul \
  --winner A \
  --rationale "A obeys the hard constraint"

python annotate.py summarize
```

Committed examples under `feedback/examples/` are **lab illustrations**, not production quality claims.

## Promotion gate (baseline vs candidate)

Policy: `gates/smoke_promote_v1.json`.

Automatic rules (lab defaults):
- candidate transport `errors == 0`
- `pass_rate >= 0.66`
- pass-rate delta vs baseline not worse than `-0.34`
- hard cases must PASS: `smoke-greeting-es`, `smoke-json-keys`
- `smoke-refusal-length` is a **soft** case (observed, does not block alone)

Human rules are optional (`--human`). Pairwise convention when used: **A = candidate**, **B = baseline**. Missing human data → rules **skip** (do not false-block).

Exit codes: `0` promote, `1` block, `2` bad usage/missing files.

## Unit tests & CI

```bash
PYTHONPATH=.. pytest -v
```

GitHub Actions workflow `.github/workflows/evals-ci.yml` runs these unit tests on changes under `evals/**`. It does **not** call a live model.

## Out of scope here

- GPU benchmark tables / Vast.ai runs (separate milestone)
- Model registry / MLflow artifact store
- Auth, multi-tenant annotation UI
