"""Roll every graded submission into one ranked table.

Reads the accumulated per-candidate records kept on the grading ledger branch,
so the table lists everyone who has ever been graded rather than only whoever
was scored in the current run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Columns always shown, even before anyone has used them, so the table shape
# does not change as attempts come in. Keep in step with MAX_GRADED in
# .github/workflows/grade.yml.
MAX_ATTEMPTS = 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scores_dir", help="directory of <candidate>.json records")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = []
    for f in sorted(Path(args.scores_dir).glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        attempts = [a for a in d.get("attempts", []) if a.get("p80_error_ms") is not None]
        if not attempts:
            continue
        best = min(a["p80_error_ms"] for a in attempts)
        latest = max(attempts, key=lambda a: a.get("n", 0))
        rows.append({
            "name": f.stem,
            "best": best,
            "all": [(a.get("n"), a["p80_error_ms"]) for a in sorted(
                attempts, key=lambda a: a.get("n", 0))],
            "n": latest.get("n_scored"),
            "missing": latest.get("n_missing_predictions", 0),
        })

    # Ranked on p80 rather than the mean: a mean rewards a method that does
    # well on easy clips and blows up on hard ones, and at this sample size a
    # small difference in the mean is not a real difference. p80 over p90
    # because with 80 clips the p90 rests on the 8th-worst clip alone.
    #
    # Ranked on a candidate's BEST attempt, not their latest. They are told how
    # many attempts they get, so penalising them for having used one to explore
    # would just discourage using them.
    rows.sort(key=lambda r: r["best"])

    def cell(v):
        return "—" if v is None else f"{v:.1f}"

    # One column per attempt, so a candidate's 1st, 2nd and 3rd are all
    # visible side by side rather than squashed into one cell.
    max_n = max((n for r in rows for n, _ in r["all"]), default=MAX_ATTEMPTS)
    max_n = max(max_n, MAX_ATTEMPTS)
    headers = ["#", "submission", "best p80 (ms)"] +               [f"attempt {k}" for k in range(1, max_n + 1)] + ["clips scored"]
    lines = ["## Leaderboard", "",
             "Ranked by p80 error (lower is better) — the error your worst "
             "20% of clips stay under. Best attempt counts.", "",
             "| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for i, r in enumerate(rows, 1):
        by_n = dict(r["all"])
        cells = [cell(by_n.get(k)) for k in range(1, max_n + 1)]
        flag = f" ⚠️ {r['missing']} missing" if r["missing"] else ""
        lines.append(f"| {i} | {r['name']} | **{cell(r['best'])}** | "
                     + " | ".join(cells)
                     + f" | {r['n']}{flag} |")
    if not rows:
        lines.append("| — | _no scored submissions yet_ |"
                     + "".join(" |" for _ in headers[2:]))

    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
