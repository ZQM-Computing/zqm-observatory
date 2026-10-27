#!/usr/bin/env python3
"""Create a signed checkpoint for a validated release-history head.

Run this only in the separately controlled anchor trust domain. This tool does
not make a local checkpoint independent merely by signing it.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # pragma: no cover
    serialization = None
    Ed25519PrivateKey = None

try:
    from scripts.release_history import canonical_json, load_entries
except ModuleNotFoundError:
    from release_history import canonical_json, load_entries

CHECKPOINT_TYPE = "zqm_observatory_history_checkpoint"


def create_checkpoint(
    history_path: Path,
    private_key_path: Path,
    output_path: Path,
    *,
    history_id: str,
    issuer: str,
    issued_at: datetime | None = None,
) -> list[str]:
    """Write a new checkpoint without overwriting an existing checkpoint file."""
    if Ed25519PrivateKey is None or serialization is None:
        return ["cryptography is required; install requirements-security.txt"]
    if not isinstance(history_id, str) or not history_id.strip():
        return ["history_id must be a non-empty stable identifier"]
    if not isinstance(issuer, str) or not issuer.strip():
        return ["issuer must be a non-empty signer identity"]
    if output_path.exists() or output_path.is_symlink():
        return ["output already exists; refusing to overwrite a checkpoint"]
    entries, errors = load_entries(history_path)
    if errors:
        return ["history is invalid; checkpoint not created", *errors]
    if not entries:
        return ["empty history cannot be checkpointed"]
    try:
        key_data = private_key_path.read_bytes()
        private_key = serialization.load_pem_private_key(key_data, password=None)
    except (OSError, ValueError, TypeError) as exc:
        return [f"private key cannot be loaded (unencrypted PEM expected): {exc}"]
    if not isinstance(private_key, Ed25519PrivateKey):
        return ["private key must be Ed25519"]
    public_key = private_key.public_key()
    raw_public = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(raw_public).hexdigest()
    timestamp = issued_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return ["issued_at must be timezone-aware"]
    payload = {
        "schema_version": 1,
        "checkpoint_type": CHECKPOINT_TYPE,
        "history_id": history_id,
        "sequence": len(entries),
        "entry_sha256": entries[-1]["entry_sha256"],
        "issued_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "issuer": issuer,
        "algorithm": "Ed25519",
        "key_fingerprint": fingerprint,
    }
    envelope = {
        "payload": payload,
        "signature": base64.b64encode(private_key.sign(canonical_json(payload))).decode("ascii"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=output_path.parent,
            prefix=f".{output_path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temp_name = stream.name
            json.dump(envelope, stream, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Avoid silently replacing a checkpoint that another process created.
        # Hard-link publication is atomic and fails if the destination exists.
        os.link(temp_name, output_path)
        os.unlink(temp_name)
        temp_name = None
    except FileExistsError:
        return ["output already exists; refusing to overwrite a checkpoint"]
    except OSError as exc:
        return [f"checkpoint output failed: {exc}"]
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
    print(f"Created signed checkpoint sequence {payload['sequence']} for history {history_id!r}.")
    print("Only treat it as an external anchor if this command ran in a separately controlled trust domain.")
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--private-key", required=True, type=Path, help="separately controlled Ed25519 private-key PEM")
    parser.add_argument("--output", required=True, type=Path, help="new checkpoint path; existing files are never overwritten")
    parser.add_argument("--history-id", required=True, help="stable configured history identifier")
    parser.add_argument("--issuer", required=True, help="stable identity of the checkpoint signer")
    args = parser.parse_args()
    errors = create_checkpoint(
        args.history, args.private_key, args.output,
        history_id=args.history_id, issuer=args.issuer,
    )
    if errors:
        print("CHECKPOINT CREATION BLOCKED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
