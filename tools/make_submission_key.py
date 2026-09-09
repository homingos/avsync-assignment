"""Grader side, run ONCE: create the submission keypair.

    python3 tools/make_submission_key.py

Writes the public half to tools/submission_key.pub (commit it) and prints the
private half (never commit it -- store it as the SUBMISSION_PRIVKEY_B64
repository secret, and keep a copy somewhere safe).

If you lose the private key you cannot read any submission sealed to it, and
every candidate has to resubmit. If you rotate it, submissions sealed to the
old key stop opening -- so rotate only between hiring rounds.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from submission_crypto import generate_keypair  # noqa: E402

PUB_PATH = Path(__file__).resolve().parent / "submission_key.pub"


def main() -> int:
    if PUB_PATH.exists():
        print(f"{PUB_PATH} already exists.", file=sys.stderr)
        print("Overwriting it invalidates every submission sealed to the "
              "current key. Delete it by hand first if that is really what "
              "you want.", file=sys.stderr)
        return 1

    priv, pub = generate_keypair()
    PUB_PATH.write_text(pub + "\n")
    print(f"Public key  -> {PUB_PATH}   (commit this)")
    print("\nPrivate key (store as the SUBMISSION_PRIVKEY_B64 secret, do NOT commit):\n")
    print(f"  {priv}\n")
    print("Set it with:")
    print("  python3 tools/make_submission_key.py   # then, from the printed value:")
    print("  gh secret set SUBMISSION_PRIVKEY_B64")
    return 0


if __name__ == "__main__":
    sys.exit(main())
