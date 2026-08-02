# Gateway eval harness (Hito 5)

Offline evaluation of the inference gateway: versioned cases → call `/chat` → automatic checks → JSON report → optional **human feedback** (rubrics / pairwise).

This is **quality** evaluation (did the answer satisfy expectations?), not serving benchmarks (TTFT/TPOT). Those live under the gateway `/metrics`.

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

Heuristic and structural checks are automatic. Human rubrics / pairwise preferences capture quality dimensions those checks miss (see below).

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

## Human feedback (rubrics / pairwise)

Automatic checks do not measure “was this answer good?”. Human feedback fills that gap with:

1. **Rubric scores** (1–5) against versioned criteria with behavioral anchors — see `rubrics/response_quality_v1.json`.
2. **Pairwise preference** (A / B / tie) with randomized on-screen order (`order_presented` is stored to document position bias controls).

### Score a response from a smoke report

```bash
# Non-interactive (scriptable)
python annotate.py rubric \
  --report reports/smoke_XXXX.json \
  --case-id smoke-refusal-length \
  --rater-id raul \
  --scores '{"instruction_following":1,"clarity":4,"concision":2,"safety_basic":5}' \
  --notes "Model ignored solo OK"

# Interactive (TTY): omit --scores; anchors are printed per criterion
python annotate.py rubric --report reports/smoke_XXXX.json \
  --case-id smoke-refusal-length --rater-id raul
```

Writes JSONL under `feedback/rubric/` (gitignored).

### Pairwise preference

```bash
python annotate.py pairwise \
  --prompt "Di solo la palabra OK." \
  --a "OK" \
  --b "Por supuesto, aquí tienes la confirmación..." \
  --rater-id raul \
  --winner A \
  --rationale "A obeys the hard constraint"
```

By default the CLI shuffles display order; pass `--no-shuffle` only for debugging.

### Summarize

```bash
python annotate.py summarize
```

Includes local annotations plus committed samples under `feedback/examples/`. Output: criterion means, simple inter-rater agreement when ≥2 raters scored the same case/response, pairwise win rates.

Committed examples are **lab illustrations**, not production quality claims.

## Promotion gate (baseline vs candidate)

A **promotion gate** decides whether a **candidate** run may replace a **baseline** under a versioned policy (`gates/smoke_promote_v1.json`).

Automatic rules (lab defaults):
- candidate transport `errors == 0`
- `pass_rate >= 0.66`
- pass-rate delta vs baseline not worse than `-0.34`
- hard cases must PASS: `smoke-greeting-es`, `smoke-json-keys`
- `smoke-refusal-length` is a **soft** case (observed, does not block alone — real CPU flakiness)

Human rules are optional (`--human`). Lab pairwise convention when used: **A = candidate**, **B = baseline**. If human data is missing, those rules **skip** (do not false-block).

### Dry-run with committed fixtures (no gateway)

```bash
# Expect PROMOTE (exit 0)
python promote_gate.py \
  --policy gates/smoke_promote_v1.json \
  --baseline gates/fixtures/baseline_smoke.json \
  --candidate gates/fixtures/candidate_smoke_promote.json
echo "exit=$?"

# Expect BLOCK (exit 1) — JSON hard case failed
python promote_gate.py \
  --policy gates/smoke_promote_v1.json \
  --baseline gates/fixtures/baseline_smoke.json \
  --candidate gates/fixtures/candidate_smoke_block.json
echo "exit=$?"
```

### Live lab flow

```bash
# Run A → save as baseline
python run_eval.py --suite smoke
cp reports/smoke_XXXX.json reports/smoke_baseline.json

# Change model/backend, run B → candidate
python run_eval.py --suite smoke
cp reports/smoke_YYYY.json reports/smoke_candidate.json

python promote_gate.py \
  --baseline reports/smoke_baseline.json \
  --candidate reports/smoke_candidate.json
```

Exit codes: `0` promote, `1` block, `2` bad usage/missing files. Decision JSON under `reports/gates/`.

## Unit tests (no gateway)

From `evals/` with `.venv-evals` active:

```bash
PYTHONPATH=.. pytest -v
```

## Next (same hito)

- Docs/demo polish for the full eval + feedback + gate loop
