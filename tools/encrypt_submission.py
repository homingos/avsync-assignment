"""Package and encrypt your submission. Run this before you commit.

    python3 tools/encrypt_submission.py submissions/YOUR_GITHUB_USERNAME

It checks your predictions are valid, bundles your folder, encrypts it so only
the graders can read it, and leaves a single `submission.enc` behind. Commit
that file and nothing else.

Why encrypted: pull requests on a public repository are readable by anyone, so
without this every candidate could read your answers and your code. The blob
protects your work.

Because the graders cannot read your submission until after they decrypt it,
the format check that used to run on your pull request now runs HERE instead.
That is why this script refuses to package an invalid submission -- it is the
last point at which a mistake is cheap to fix.
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from submission_crypto import seal  # noqa: E402

REQUIRED = ("predictions.json", "METHOD.md")
RUN_SCRIPTS = ("run.py", "run.sh")
OUT_NAME = "submission.enc"
# A real submission is three text files. Anything far larger means clips or a
# virtualenv got swept in, which would also blow past GitHub's file limits.
MAX_BUNDLE_BYTES = 5 * 1024 * 1024


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="your submission folder, e.g. submissions/octocat")
    ap.add_argument("--clip-ids", default="heldout_clip_ids.txt")
    ap.add_argument(
        "--key",
        default=str(Path(__file__).resolve().parent / "submission_key.pub"),
        help="grader public key (ships with this repo)",
    )
    ap.add_argument(
        "--skip-validation",
        action="store_true",
        help="package even if the format check fails. You almost certainly do "
             "not want this: an unreadable submission cannot be scored.",
    )
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"No such folder: {folder}", file=sys.stderr)
        return 1

    missing = [f for f in REQUIRED if not (folder / f).is_file()]
    if not any((folder / r).is_file() for r in RUN_SCRIPTS):
        missing.append("run.py (or run.sh)")
    if missing:
        print("Your submission folder is missing:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1

    # Validate before sealing. Once encrypted nobody can tell you it is broken.
    if not args.skip_validation:
        rc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "validate_submission.py"),
             "--predictions", str(folder / "predictions.json"),
             "--clip-ids", args.clip_ids],
        ).returncode
        if rc != 0:
            print("\nNot packaging: fix the problems above and run this again.",
                  file=sys.stderr)
            return 1
        print()

    # Bundle every file in the folder EXCEPT a previous submission.enc, so
    # re-running does not nest one sealed blob inside the next.
    payload = io.BytesIO()
    included = []
    with tarfile.open(fileobj=payload, mode="w:gz") as tar:
        for p in sorted(folder.rglob("*")):
            if not p.is_file() or p.name == OUT_NAME:
                continue
            tar.add(p, arcname=str(p.relative_to(folder)))
            included.append(str(p.relative_to(folder)))
    raw = payload.getvalue()

    if len(raw) > MAX_BUNDLE_BYTES:
        print(f"Bundle is {len(raw)/1e6:.1f}MB, over the "
              f"{MAX_BUNDLE_BYTES/1e6:.0f}MB limit.", file=sys.stderr)
        print("Did a clip, a virtualenv or a __pycache__ end up in the folder?",
              file=sys.stderr)
        return 1

    pub = Path(args.key).read_text().strip()
    blob = seal(raw, pub)
    out = folder / OUT_NAME
    out.write_bytes(blob)

    print(f"Packaged {len(included)} file(s):")
    for name in included:
        print(f"  {name}")
    print(f"\nEncrypted -> {out}  ({len(blob)} bytes)")
    print("\nCommit ONLY this file:")
    print(f"  git add {out}")
    print(f"  git commit -m 'Submission: {folder.name}'")
    print("\nKeep your unencrypted files locally. Do not commit them -- the "
          "check on your pull request will reject them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
