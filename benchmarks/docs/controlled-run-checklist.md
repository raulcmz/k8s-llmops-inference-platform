# Controlled-run checklist

A **controlled run** means: you change one thing at a time, write down the setup, and only then trust the numbers.

Use this every time before you paste results into notes or a README.

---

## Who does what

| Step | Who |
|---|---|
| Follow this checklist and fill the results template | **You on the VM** (your Ubuntu lab) |
| Keep these docs updated in git | Agent / PR process |

---

## Before you start

- [ ] Write **metadata** (copy into `--metadata` JSON and into the results template):
  - [ ] `hardware` (e.g. `cpu-lab`, or GPU name if cloud)
  - [ ] `backend` (`ollama` or `vllm`)
  - [ ] `model` (exact tag)
  - [ ] `git_commit` (`git rev-parse --short HEAD`)
  - [ ] `cold_or_warm` (`cold` = first answers after idle/load; `warm` = after a few chats)
  - [ ] date (UTC)
- [ ] Gateway is up: `/health` and `/ready` return OK  
  (**You on the VM**)
- [ ] Nobody else is hammering the same model (shared PC = noisy numbers)
- [ ] If using paid GPU (Vast.ai later): note **$/hour** and plan to **stop** the instance after the run

## During the run

- [ ] Change **only one** variable (e.g. concurrency), not model + concurrency + prompt at once
- [ ] Prefer a fixed `case-id` for concurrency sweeps (`bench-short-es`)
- [ ] Keep `requests-per-level` modest on CPU (3 is fine for lab)
- [ ] Do not restart Ollama / swap models mid-sweep
- [ ] Save the command you ran (copy/paste into the template)

## After the run

- [ ] JSON report exists under `benchmarks/reports/` (gitignored — local artifact)
- [ ] If sweep: Markdown table `.md` exists next to it
- [ ] Copy key metrics into [`results-template.md`](results-template.md) (see metrics list there)
- [ ] Optional: peek at gateway Prometheus for comparison  
  (**You on the VM**) `curl -s http://127.0.0.1:8080/metrics | rg 'llm_ttft|llm_tpot|llm_errors|llm_request_duration'`
- [ ] Label honestly: CPU lab ≠ GPU blog post
- [ ] Paid GPU? **Stop/destroy** the instance

## Do not

- [ ] Publish a TTFT number without metadata
- [ ] Mix Ollama-on-CPU rows with vLLM-on-GPU rows in one table without clear labels
- [ ] Commit huge raw `reports/*.json` dumps by habit (prefer a short filled template)
- [ ] Invent GPU numbers “for the README”

## Related docs

- Full metric definitions: [`metrics.md`](metrics.md)
- Empty results form: [`results-template.md`](results-template.md)
