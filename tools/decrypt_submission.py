"""Grader side: open a sealed submission.

    SUBMISSION_PRIVKEY_B64=... python3 tools/decrypt_submission.py \
        submissions/octocat/submission.enc --out-dir /tmp/octocat

Used by the grading workflow, and usable by hand when scoring locally.

The private key comes from the environment, never an argument, so it does not
land in shell history or a process listing.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from submission_crypto import unseal  # noqa: E402

MAX_MEMBERS = 200
MAX_TOTAL_BYTES = 20 * 1024 * 1024


def _safe_extract(raw: bytes, out_dir: Path) -> list[str]:
    """Extract the bundle, refusing anything that writes outside out_dir.

    The archive was built by a candidate, so it is untrusted input. A tar entry
    named "../../.ssh/authorized_keys" or an absolute path or a symlink would
    otherwise let a submission write anywhere the runner can reach -- and this
    job holds the truth secret.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_root = out_dir.resolve()
    names = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        members = tar.getmembers()
        if len(members) > MAX_MEMBERS:
            raise SystemExit(f"bundle has {len(members)} entries, refusing")
        total = sum(m.size for m in members)
        if total > MAX_TOTAL_BYTES:
            raise SystemExit(f"bundle expands to {total} bytes, refusing")
        for m in members:
            if m.issym() or m.islnk():
                raise SystemExit(f"bundle contains a link entry ({m.name}), refusing")
            if not m.isfile() and not m.isdir():
                raise SystemExit(f"bundle contains a special entry ({m.name}), refusing")
            target = (out_dir / m.name).resolve()
            if not str(target).startswith(str(resolved_root) + os.sep) and target != resolved_root:
                raise SystemExit(f"bundle entry escapes the output directory: {m.name}")
            names.append(m.name)
        # filter="data" is Python 3.12+; it rejects links, absolute paths and
        # traversal in the stdlib itself. The explicit checks above already
        # cover those, so on older Pythons we fall through to them rather than
        # failing. Passing it where available means the stdlib and our own
        # guards both have to be wrong for an escape to happen.
        try:
            tar.extractall(out_dir, filter="data")
        except TypeError:
            tar.extractall(out_dir)
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("blob")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    key = os.environ.get("SUBMISSION_PRIVKEY_B64", "")
    if not key:
        print("SUBMISSION_PRIVKEY_B64 is not set.", file=sys.stderr)
        print("Generate a keypair with tools/make_submission_key.py if you have "
              "not yet.", file=sys.stderr)
        return 1

    blob = Path(args.blob).read_bytes()
    try:
        raw = unseal(blob, key)
    except Exception as exc:
        # Most likely causes: sealed to a different (older) grader key, or the
        # file was truncated by a mid-push failure.
        print(f"Could not decrypt {args.blob}: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1

    names = _safe_extract(raw, Path(args.out_dir))
    print(f"Decrypted {args.blob} -> {args.out_dir}")
    for n in sorted(names):
        print(f"  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
