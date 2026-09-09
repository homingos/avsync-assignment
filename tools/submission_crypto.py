"""Seal a submission so only the graders can read it.

WHY THIS EXISTS
---------------
Submissions arrive as pull requests to a public repository, and a pull request
diff on a public repo is readable by anyone -- no login, no cookies. Without
this, every candidate can read the answers of everyone who submitted before
them, and can read their `run.py`, which is worth just as much to a copier as
the predictions themselves.

Encrypting the whole submission bundle removes the incentive rather than
policing the outcome: what lands in git is an opaque blob.

SCHEME
------
Anonymous sealed box, X25519 + HKDF-SHA256 + AES-256-GCM:

  1. The grader holds a long-term X25519 keypair. The PUBLIC half ships in this
     repository as `tools/submission_key.pub`; the private half exists only as
     a repository secret and on the grader's machine.
  2. The sender generates a single-use ("ephemeral") X25519 keypair, does an
     ECDH with the grader's public key, and runs the shared secret through
     HKDF to get a 256-bit AES key.
  3. The bundle is encrypted with AES-256-GCM. The ephemeral PUBLIC key is
     written into the file so the grader can redo step 2; the ephemeral private
     key is discarded and never leaves the sender's machine.

Properties worth being explicit about:

  - Only the holder of the grader's private key can decrypt. Other candidates,
    and anyone reading the public repo, see random bytes.
  - Each submission uses a fresh ephemeral key, so two candidates who submit
    byte-identical predictions still produce completely different ciphertext.
    Without that, identical blobs would reveal copying between candidates --
    but it would equally reveal that a candidate resubmitted unchanged work.
  - GCM authenticates, so a corrupted or tampered blob fails loudly at decrypt
    rather than yielding garbage that scores badly.
  - This is anonymous: the file does NOT prove who sent it. That is fine here,
    because GitHub already tells us who opened the pull request, and the
    validation workflow requires the folder name to match the PR author.

The file format is deliberately boring, so a failure is easy to diagnose:

  magic      8 bytes   b"AVSYNC01"
  ephemeral 32 bytes   sender's single-use X25519 public key
  nonce     12 bytes   AES-GCM nonce
  ciphertext rest      AES-256-GCM(bundle) with the tag appended
"""
from __future__ import annotations

import base64

# cryptography is imported lazily, inside the functions that need it. The
# pull-request validation workflow runs with no dependencies installed (it is
# a fork-PR job with no secrets and nothing to install) and only ever calls
# looks_sealed(), which is pure byte inspection. A module-level import would
# force that job to install a wheel it has no use for.

MAGIC = b"AVSYNC01"
EPH_LEN = 32
NONCE_LEN = 12
# Binds the derived key to this specific application, so a key agreed here can
# never be confused with one agreed for some other purpose using the same
# keypair.
HKDF_INFO = b"avsync submission v1"


def _crypto():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey, X25519PublicKey,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return hashes, X25519PrivateKey, X25519PublicKey, AESGCM, HKDF


def _derive(shared: bytes, eph_pub: bytes, grader_pub: bytes) -> bytes:
    """Turn the raw ECDH output into an AES key.

    Both public keys go into the HKDF input, not just the shared secret. That
    binds the derived key to this exact pair of keys, which is what stops a
    blob sealed to one grader key being replayed against another.
    """
    hashes, _, _, _, HKDF = _crypto()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=HKDF_INFO + eph_pub + grader_pub,
    ).derive(shared)


def seal(plaintext: bytes, grader_pub_b64: str) -> bytes:
    """Encrypt `plaintext` so only the grader's private key can open it."""
    _, X25519PrivateKey, X25519PublicKey, AESGCM, _ = _crypto()
    grader_pub_raw = base64.b64decode(grader_pub_b64)
    if len(grader_pub_raw) != EPH_LEN:
        raise ValueError(
            f"grader public key must be {EPH_LEN} raw bytes, got {len(grader_pub_raw)}"
        )
    grader_pub = X25519PublicKey.from_public_bytes(grader_pub_raw)

    eph_priv = X25519PrivateKey.generate()
    eph_pub_raw = eph_priv.public_key().public_bytes_raw()
    key = _derive(eph_priv.exchange(grader_pub), eph_pub_raw, grader_pub_raw)

    # A fresh random key per submission means a fixed nonce would be safe, but
    # a random one costs nothing and removes the need for that argument.
    import os

    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return MAGIC + eph_pub_raw + nonce + ct


def unseal(blob: bytes, grader_priv_b64: str) -> bytes:
    """Decrypt a sealed submission. Raises on tampering or the wrong key."""
    _, X25519PrivateKey, X25519PublicKey, AESGCM, _ = _crypto()
    header = len(MAGIC) + EPH_LEN + NONCE_LEN
    if len(blob) < header + 16:
        raise ValueError(
            f"sealed submission is only {len(blob)} bytes -- too short to be valid"
        )
    if blob[: len(MAGIC)] != MAGIC:
        raise ValueError(
            f"not a sealed submission: expected magic {MAGIC!r}, "
            f"got {blob[: len(MAGIC)]!r}"
        )

    eph_pub_raw = blob[len(MAGIC) : len(MAGIC) + EPH_LEN]
    nonce = blob[len(MAGIC) + EPH_LEN : header]
    ct = blob[header:]

    grader_priv = X25519PrivateKey.from_private_bytes(
        base64.b64decode(grader_priv_b64)
    )
    grader_pub_raw = grader_priv.public_key().public_bytes_raw()
    eph_pub = X25519PublicKey.from_public_bytes(eph_pub_raw)
    key = _derive(grader_priv.exchange(eph_pub), eph_pub_raw, grader_pub_raw)

    # Raises InvalidTag if the blob was altered or sealed to a different key.
    return AESGCM(key).decrypt(nonce, ct, None)


def looks_sealed(blob: bytes) -> bool:
    """Cheap structural check usable WITHOUT the private key.

    The pull-request validation workflow runs on fork PRs and therefore has no
    secrets at all, so this is the most it can say about a submission: that the
    file is shaped like a sealed bundle rather than, say, plaintext JSON.
    """
    return len(blob) >= len(MAGIC) + EPH_LEN + NONCE_LEN + 16 and blob[
        : len(MAGIC)
    ] == MAGIC


def generate_keypair() -> tuple[str, str]:
    """Return (private_b64, public_b64). Run once, by the grader."""
    _, X25519PrivateKey, _, _, _ = _crypto()
    priv = X25519PrivateKey.generate()
    return (
        base64.b64encode(priv.private_bytes_raw()).decode(),
        base64.b64encode(priv.public_key().public_bytes_raw()).decode(),
    )
