"""Append one graded attempt to a candidate's running record.

    python3 tools/record_attempt.py --name octocat --attempt 2 \
        --summary results/octocat.json --scores-dir ledger/scores

The records live on the grading ledger branch, which is what lets the
leaderboard show every candidate who has ever been graded. Without them it
could only show whoever was scored in the current run -- and grading a pull
request grades exactly one submission, so that would be a one-row table.

Only the published summary is stored: the score and the clip counts. Nothing
per-clip and nothing per-regime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--attempt", type=int, required=True)
    ap.add_argument("--summary", required=True, help="the redacted score report")
    ap.add_argument("--scores-dir", required=True)
    args = ap.parse_args()

    summary = json.loads(Path(args.summary).read_text())
    out_dir = Path(args.scores_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.name}.json"

    record = json.loads(path.read_text()) if path.exists() else {"attempts": []}
    # Replace rather than append when this attempt number is already present,
    # so re-running a grade does not duplicate a row.
    record["attempts"] = [a for a in record["attempts"]
                          if a.get("n") != args.attempt]
    record["attempts"].append({
        "n": args.attempt,
        "p80_error_ms": summary["p80_error_ms"],
        "n_scored": summary.get("n_scored"),
        "n_missing_predictions": summary.get("n_missing_predictions", 0),
    })
    record["attempts"].sort(key=lambda a: a["n"])
    path.write_text(json.dumps(record, indent=1))

    print(f"  recorded attempt {args.attempt} for {args.name}: "
          f"p80 {summary['p80_error_ms']:.2f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
