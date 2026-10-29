"""Run the golden question set against the text-to-SQL pipeline, one by one.

From the project root:
    python -m tests.run_golden --build            # (re)create tests/golden_expected.json
    python -m tests.run_golden                    # run all 20 questions
    python -m tests.run_golden --id 17            # run a single question
    python -m tests.run_golden --difficulty hard  # run one difficulty level

A question passes when every column of the reference answer appears in the
generated answer with identical values in the same row order. Extra columns
are allowed. Numbers are compared rounded to 2 decimals.
"""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

from src.db import run_query
from src.llm import generate_sql
from tests.golden_questions import GOLDEN

EXPECTED_PATH = Path(__file__).resolve().parent / "golden_expected.json"


def _norm(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return str(value)


def to_columns(df: pd.DataFrame) -> list[list]:
    """Return the DataFrame as a list of normalized columns."""
    return [[_norm(v) for v in df[col].tolist()] for col in df.columns]


def matches_expected(actual_cols: list[list], expected_cols: list[list]) -> bool:
    if not expected_cols:
        return not actual_cols
    if len(actual_cols) < len(expected_cols):
        return False
    remaining = list(actual_cols)
    for exp_col in expected_cols:
        for i, act_col in enumerate(remaining):
            if act_col == exp_col:
                remaining.pop(i)
                break
        else:
            return False
    return True


def build_expected() -> None:
    expected = {}
    for g in GOLDEN:
        _, df = run_query(g["sql"])
        expected[str(g["id"])] = to_columns(df)
    EXPECTED_PATH.write_text(json.dumps(expected, indent=1))
    print(f"Wrote reference answers for {len(expected)} questions to {EXPECTED_PATH}")


def short(cols: list[list], limit: int = 6) -> str:
    rows = list(zip(*cols))
    text = str(rows[:limit])
    return text + (f" ... ({len(rows)} rows)" if len(rows) > limit else "")


def run(selected: list[dict]) -> None:
    expected = json.loads(EXPECTED_PATH.read_text())
    results = defaultdict(lambda: [0, 0])  # difficulty -> [passed, total]
    failures = []

    for g in selected:
        print(f"\n[{g['id']:>2}] ({g['difficulty']}) {g['question']}")
        start = time.monotonic()
        generated = ""
        try:
            generated = generate_sql(g["question"])
            final_sql, df = run_query(generated)
            ok = matches_expected(to_columns(df), expected[str(g["id"])])
            detail = "" if ok else f"expected {short(expected[str(g['id'])])}\n       got      {short(to_columns(df))}"
        except Exception as e:  # any failure counts as a miss, with the reason
            ok, detail = False, f"{type(e).__name__}: {e}"
        elapsed = time.monotonic() - start

        results[g["difficulty"]][1] += 1
        results[g["difficulty"]][0] += ok
        print(f"     {'PASS' if ok else 'FAIL'} ({elapsed:.1f}s)")
        print(f"     SQL: {generated}")
        if not ok:
            print(f"     {detail}")
            failures.append(g["id"])

    print("\n===== Summary =====")
    total_pass = total = 0
    for level in ("simple", "moderate", "hard"):
        if level in results:
            p, t = results[level]
            print(f"{level:<9} {p}/{t}")
            total_pass += p
            total += t
    print(f"{'overall':<9} {total_pass}/{total}")
    if failures:
        print(f"Failed ids: {failures}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="regenerate reference answers")
    parser.add_argument("--id", type=int, help="run a single question id")
    parser.add_argument("--difficulty", choices=["simple", "moderate", "hard"])
    args = parser.parse_args()

    if args.build:
        build_expected()
        return

    selected = GOLDEN
    if args.id is not None:
        selected = [g for g in GOLDEN if g["id"] == args.id]
    elif args.difficulty:
        selected = [g for g in GOLDEN if g["difficulty"] == args.difficulty]
    if not selected:
        raise SystemExit("No matching questions.")
    run(selected)


if __name__ == "__main__":
    main()
