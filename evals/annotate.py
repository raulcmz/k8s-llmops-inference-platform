#!/usr/bin/env python3
"""CLI: capture human rubric / pairwise feedback for gateway evals.

Examples:
  python annotate.py rubric --report reports/smoke_....json \\
      --case-id smoke-refusal-length --rater-id raul \\
      --scores '{"instruction_following":2,"clarity":4,"concision":2,"safety_basic":5}'

  python annotate.py pairwise --prompt "Di solo la palabra OK." \\
      --a "OK" --b "Claro, la respuesta es OK." --rater-id raul --winner A

  python annotate.py summarize
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.harness.agreement import summarize_feedback
from evals.harness.feedback_io import (
    PairwiseAnnotation,
    RubricAnnotation,
    append_jsonl,
    load_case_from_report,
    load_feedback_dir,
    new_id,
)
from evals.harness.rubric import default_rubric_path, load_rubric, validate_scores

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_RUBRIC_OUT = EVALS_DIR / "feedback" / "rubric" / "annotations.jsonl"
DEFAULT_PAIRWISE_OUT = EVALS_DIR / "feedback" / "pairwise" / "annotations.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Human feedback annotation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    rubric = sub.add_parser("rubric", help="Score a response with a rubric")
    rubric.add_argument("--rubric", default=str(default_rubric_path()), help="Rubric JSON path")
    rubric.add_argument("--report", help="Eval report JSON (from run_eval.py)")
    rubric.add_argument("--case-id", help="Case id inside the report")
    rubric.add_argument("--prompt", default=None, help="Prompt text (if not using --report)")
    rubric.add_argument("--response", default=None, help="Response text (if not using --report)")
    rubric.add_argument("--rater-id", required=True)
    rubric.add_argument(
        "--scores",
        default=None,
        help="JSON object of criterion→int (skip interactive prompts)",
    )
    rubric.add_argument("--notes", default="")
    rubric.add_argument("--out", default=str(DEFAULT_RUBRIC_OUT))

    pairwise = sub.add_parser("pairwise", help="Prefer response A or B")
    pairwise.add_argument("--prompt", required=True)
    pairwise.add_argument("--a", required=True, dest="response_a", help="Response A")
    pairwise.add_argument("--b", required=True, dest="response_b", help="Response B")
    pairwise.add_argument("--case-id", default=None)
    pairwise.add_argument("--rater-id", required=True)
    pairwise.add_argument(
        "--winner",
        choices=["A", "B", "tie"],
        default=None,
        help="Winner in original A/B labels (skip interactive)",
    )
    pairwise.add_argument("--rationale", default="")
    pairwise.add_argument(
        "--no-shuffle",
        action="store_true",
        help="Do not randomize on-screen order (default: shuffle to reduce position bias)",
    )
    pairwise.add_argument("--out", default=str(DEFAULT_PAIRWISE_OUT))

    summarize = sub.add_parser("summarize", help="Aggregate feedback JSONL")
    summarize.add_argument(
        "--rubric-dir",
        default=str(EVALS_DIR / "feedback" / "rubric"),
    )
    summarize.add_argument(
        "--pairwise-dir",
        default=str(EVALS_DIR / "feedback" / "pairwise"),
    )
    summarize.add_argument(
        "--examples-dir",
        default=str(EVALS_DIR / "feedback" / "examples"),
        help="Also include committed example JSONL files",
    )

    return parser.parse_args()


def _prompt_scores_interactive(rubric) -> dict[str, int]:
    print(f"rubric={rubric.id} scale={rubric.scale.min}-{rubric.scale.max}")
    scores: dict[str, int] = {}
    for criterion in rubric.criteria:
        print()
        print(f"[{criterion.id}] {criterion.name}")
        print(f"  {criterion.description}")
        for anchor_key in sorted(criterion.anchors.keys(), key=int):
            print(f"  {anchor_key}: {criterion.anchors[anchor_key]}")
        while True:
            raw = input(f"  score ({rubric.scale.min}-{rubric.scale.max}): ").strip()
            try:
                value = int(raw)
            except ValueError:
                print("  enter an integer")
                continue
            if rubric.scale.min <= value <= rubric.scale.max:
                scores[criterion.id] = value
                break
            print("  out of range")
    return scores


def cmd_rubric(args: argparse.Namespace) -> int:
    rubric = load_rubric(Path(args.rubric))
    source_report = None
    case_id = args.case_id

    if args.report:
        if not args.case_id:
            print("--case-id is required with --report", file=sys.stderr)
            return 2
        loaded = load_case_from_report(Path(args.report), args.case_id)
        prompt = loaded["prompt"]
        response = loaded["response"]
        source_report = loaded["source_report"]
        case_id = loaded["case_id"]
    else:
        if not args.prompt or args.response is None:
            print("provide --report/--case-id or --prompt and --response", file=sys.stderr)
            return 2
        prompt = args.prompt
        response = args.response

    print("--- prompt ---")
    print(prompt)
    print("--- response ---")
    print(response)
    print("---------------")

    if args.scores:
        scores = validate_scores(rubric, json.loads(args.scores))
    else:
        if not sys.stdin.isatty():
            print("interactive scores require a TTY, or pass --scores JSON", file=sys.stderr)
            return 2
        scores = validate_scores(rubric, _prompt_scores_interactive(rubric))

    notes = args.notes
    if not notes and sys.stdin.isatty() and not args.scores:
        notes = input("notes (optional): ").strip()

    record = RubricAnnotation(
        id=new_id("ann"),
        rubric_id=rubric.id,
        case_id=case_id,
        source_report=source_report,
        prompt=prompt,
        response=response,
        rater_id=args.rater_id,
        scores=scores,
        notes=notes,
    )
    out = Path(args.out)
    append_jsonl(out, record)
    print(f"wrote {record.id} -> {out}")
    return 0


def cmd_pairwise(args: argparse.Namespace) -> int:
    order: list[str] = ["A", "B"]
    if not args.no_shuffle:
        random.shuffle(order)

    display = {
        "A": args.response_a,
        "B": args.response_b,
    }
    print("--- prompt ---")
    print(args.prompt)
    print(f"--- first on screen (logical {order[0]}) ---")
    print(display[order[0]])
    print(f"--- second on screen (logical {order[1]}) ---")
    print(display[order[1]])
    print("---------------")
    print("Pick winner by logical label A/B (not screen order), or tie.")

    if args.winner:
        winner = args.winner
    else:
        if not sys.stdin.isatty():
            print("interactive winner requires a TTY, or pass --winner", file=sys.stderr)
            return 2
        while True:
            raw = input("winner [A/B/tie]: ").strip().lower()
            if raw in {"a", "b", "tie"}:
                winner = "tie" if raw == "tie" else raw.upper()
                break
            print("enter A, B, or tie")

    rationale = args.rationale
    if not rationale and sys.stdin.isatty() and not args.winner:
        rationale = input("rationale (optional): ").strip()

    record = PairwiseAnnotation(
        id=new_id("pw"),
        case_id=args.case_id,
        prompt=args.prompt,
        response_a=args.response_a,
        response_b=args.response_b,
        order_presented=order,  # type: ignore[arg-type]
        winner=winner,  # type: ignore[arg-type]
        rater_id=args.rater_id,
        rationale=rationale,
    )
    out = Path(args.out)
    append_jsonl(out, record)
    print(f"wrote {record.id} order_presented={order} -> {out}")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    from evals.harness.feedback_io import load_jsonl

    rubric_rows = load_feedback_dir(Path(args.rubric_dir))
    pairwise_rows = load_feedback_dir(Path(args.pairwise_dir))
    examples_dir = Path(args.examples_dir)
    if examples_dir.is_dir():
        for path in sorted(examples_dir.glob("*.jsonl")):
            for row in load_jsonl(path):
                kind = row.get("kind")
                if kind == "rubric":
                    rubric_rows.append(row)
                elif kind == "pairwise":
                    pairwise_rows.append(row)

    summary = summarize_feedback(rubric_rows, pairwise_rows)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "rubric":
        return cmd_rubric(args)
    if args.command == "pairwise":
        return cmd_pairwise(args)
    if args.command == "summarize":
        return cmd_summarize(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
