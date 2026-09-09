"""Roll per-submission score reports into one ranked table."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = []
    for f in sorted(Path(args.results_dir).glob("*.json")):
        if f.name == "LEADERBOARD.md":
            continue
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if "p80_error_ms" not in d:
            continue
        # Published results carry the score alone. See score.py redacted().
        rows.append({
            "name": f.stem,
            "p80": d["p80_error_ms"],
            "n": d.get("n_scored"),
            "missing": d.get("n_missing_predictions", 0),
        })
    # Ranked on p80, not the mean. Two reasons, both measured on our own
    # reference solutions over 80 clips:
    #   - The mean and the tail disagree about which method is better. A
    #     drift-aware estimator lost on the mean (16.04 vs 15.03) while
    #     winning every tail statistic (p80 22.08 vs 24.18). Ranking on the
    #     mean rewarded the method that does well on easy clips and blows up
    #     on hard ones.
    #   - Bootstrap 95% CIs on the mean overlap heavily at this sample size
    #     ([12.51, 17.71] vs [13.59, 18.55]), so a 1ms lead on the mean is
    #     not a real difference.
    # p80 over p90: with 80 clips the p90 rests on the 8th-worst clip alone.
    rows.sort(key=lambda r: (r["p80"] is None, r["p80"]))

    def cell(v):
        return "—" if v is None else f"{v:.1f}"

    lines = ["## Leaderboard", "",
             "Ranked by p80 error (lower is better) — the error your worst "
             "20% of clips stay under.", "",
             "| # | submission | p80 (ms) | scored |",
             "|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        flag = f" ⚠️ {r['missing']} missing" if r["missing"] else ""
        lines.append(f"| {i} | {r['name']} | **{cell(r['p80'])}** | {r['n']}{flag} |")
    if not rows:
        lines.append("| — | _no scored submissions yet_ | | |")

    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
