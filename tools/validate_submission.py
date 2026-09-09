"""
Check that a submission is READABLE and COMPLETE. Never checks accuracy.

This runs on pull requests from forks, which GitHub deliberately denies access
to repository secrets -- so the held-out answers are not available here and no
score can be computed. That separation is the point: students get fast,
unlimited format feedback without the answers ever being reachable from a
context they control.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Sanity bound only. An answer past this is a unit error (seconds given as
# milliseconds) or a runaway estimate, not a real attempt. Deliberately far
# looser than any offset in the data -- this check exists to catch mistakes,
# not to hint at the answer range.
PLAUSIBLE_MS = 400.0


def fail(msgs):
    print("SUBMISSION INVALID\n")
    for m in msgs:
        print(f"  - {m}")
    print(f"\n{len(msgs)} problem(s) found. Fix and push again to this branch.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--clip-ids", required=True,
                    help="text file, one expected held-out clip id per line")
    ap.add_argument("--quiet", action="store_true",
                    help="print only pass/fail, without the summary counts")
    args = ap.parse_args()

    errs: list[str] = []

    p = Path(args.predictions)
    if not p.exists():
        return fail([f"{p} not found"])

    try:
        raw = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        return fail([f"{p.name} is not valid JSON: {e}"])

    if isinstance(raw, dict):
        records = [{"clip_id": k, **v} for k, v in raw.items() if isinstance(v, dict)]
        if len(records) != len(raw):
            errs.append("object form must map each clip_id to an object")
    elif isinstance(raw, list):
        records = raw
    else:
        return fail([f"top level must be a JSON list (or object), got {type(raw).__name__}"])

    expected = {ln.strip() for ln in Path(args.clip_ids).read_text().splitlines() if ln.strip()}
    seen: set[str] = set()

    for i, r in enumerate(records):
        where = f"entry {i}"
        if not isinstance(r, dict):
            errs.append(f"{where}: must be an object, got {type(r).__name__}")
            continue
        cid = r.get("clip_id")
        if not isinstance(cid, str):
            errs.append(f"{where}: missing or non-string 'clip_id'")
            continue
        where = cid
        if cid in seen:
            errs.append(f"{where}: appears more than once")
        seen.add(cid)
        if cid not in expected:
            errs.append(f"{where}: not a held-out clip id")
            continue

        kind = r.get("type")
        if kind not in ("constant", "drift"):
            errs.append(f"{where}: 'type' must be \"constant\" or \"drift\", got {kind!r}")
            continue

        def num_ok(v):
            return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

        if kind == "constant":
            v = r.get("offset_ms")
            if not num_ok(v):
                errs.append(f"{where}: constant needs a finite numeric 'offset_ms'")
            elif abs(v) > PLAUSIBLE_MS:
                errs.append(f"{where}: offset_ms={v} is beyond +-{PLAUSIBLE_MS:.0f}ms "
                            f"-- are your units milliseconds?")
        else:
            has_series = "t_s" in r and "offset_ms" in r
            has_ramp = "start_ms" in r and "end_ms" in r
            if not (has_series or has_ramp):
                errs.append(f"{where}: drift needs either (t_s, offset_ms) lists "
                            f"or (start_ms, end_ms) numbers")
            elif has_series:
                ts, vs = r["t_s"], r["offset_ms"]
                if not (isinstance(ts, list) and isinstance(vs, list)):
                    errs.append(f"{where}: t_s and offset_ms must both be lists")
                elif len(ts) != len(vs):
                    errs.append(f"{where}: t_s has {len(ts)} points but offset_ms has {len(vs)}")
                elif len(ts) == 0:
                    errs.append(f"{where}: t_s is empty")
                elif not all(num_ok(x) for x in ts) or not all(num_ok(x) for x in vs):
                    errs.append(f"{where}: t_s/offset_ms contain a non-finite or non-numeric value")
                elif max(abs(float(x)) for x in vs) > PLAUSIBLE_MS:
                    errs.append(f"{where}: an offset_ms value exceeds +-{PLAUSIBLE_MS:.0f}ms "
                                f"-- are your units milliseconds?")
                elif min(float(x) for x in ts) < -1.0:
                    errs.append(f"{where}: t_s has negative times")
            else:
                if not (num_ok(r["start_ms"]) and num_ok(r["end_ms"])):
                    errs.append(f"{where}: start_ms and end_ms must be finite numbers")

    missing = sorted(expected - seen)
    if missing:
        show = ", ".join(missing[:8]) + (f" ... (+{len(missing)-8} more)" if len(missing) > 8 else "")
        errs.append(f"{len(missing)} held-out clip(s) have no prediction: {show}")

    if errs:
        return fail(errs)

    print("SUBMISSION VALID")
    if not args.quiet:
        # Detail for your own runs. The grading job passes --quiet, since its
        # output is public and we keep published results to the score alone.
        print(f"  {len(seen)} predictions, covering all {len(expected)} held-out clips")
        n_drift = sum(1 for r in records if r.get("type") == "drift")
        print(f"  {len(seen) - n_drift} marked constant, {n_drift} marked drift")
    print("\nFormat is correct and complete. This says nothing about accuracy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
