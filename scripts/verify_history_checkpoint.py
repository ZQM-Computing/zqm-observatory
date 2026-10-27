#!/usr/bin/env python3
"""Verify an independently sourced, Ed25519-signed release-history checkpoint.

This verifies a checkpoint; it does not fetch one or establish that its source is
independent. The trusted public key must be provisioned out-of-band.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - dependency failure is covered by CLI
    serialization = None
    Ed25519PublicKey = None

try:
    from scripts.release_history import load_entries, canonical_json
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from release_history import load_entries, canonical_json
    from strict_json import loads_strict


CHECKPOINT_TYPE = "zqm_observatory_history_checkpoint"
REQUIRED_PAYLOAD_FIELDS = {
    "schema_version", "checkpoint_type", "history_id", "sequence",
    "entry_sha256", "issued_at", "issuer", "algorithm", "key_fingerprint",
}


def _read_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = loads_strict(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [f"{label} cannot be read as strict JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label} must be a JSON object"]
    return value, []


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def verify_checkpoint(
    history_path: Path,
    checkpoint_path: Path,
    trusted_public_key_path: Path,
    *,
    max_age_seconds: int = 86400,
    now: datetime | None = None,
    minimum_sequence: int = 0,
    expected_history_id: str | None = None,
) -> list[str]:
    """Return validation errors; an empty list means signature and local consistency pass."""
    errors: list[str] = []
    if Ed25519PublicKey is None or serialization is None:
        return ["cryptography is required; install requirements-security.txt"]
    if type(max_age_seconds) is not int or max_age_seconds <= 0:
        return ["max_age_seconds must be a positive integer"]
    if type(minimum_sequence) is not int or minimum_sequence < 0:
        return ["minimum_sequence must be a non-negative integer"]

    checkpoint, read_errors = _read_json(checkpoint_path, "checkpoint")
    errors.extend(read_errors)
    if checkpoint is None:
        return errors
    if set(checkpoint) != {"payload", "signature"}:
        errors.append("checkpoint envelope must contain exactly payload and signature")
        return errors
    payload = checkpoint.get("payload")
    if not isinstance(payload, dict) or set(payload) != REQUIRED_PAYLOAD_FIELDS:
        errors.append("checkpoint payload fields do not match the required schema")
        return errors
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        errors.append("checkpoint schema_version must be integer 1")
    if payload.get("checkpoint_type") != CHECKPOINT_TYPE:
        errors.append("checkpoint_type is invalid")
    if payload.get("algorithm") != "Ed25519":
        errors.append("checkpoint algorithm must be Ed25519")
    for field in ("history_id", "issuer", "key_fingerprint"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            errors.append(f"checkpoint {field} must be a non-empty string")
    sequence = payload.get("sequence")
    if type(sequence) is not int or sequence < 1:
        errors.append("checkpoint sequence must be a positive integer")
    elif sequence < minimum_sequence:
        errors.append("checkpoint sequence regressed below the previously accepted sequence")
    entry_hash = payload.get("entry_sha256")
    if not isinstance(entry_hash, str) or len(entry_hash) != 64 or any(c not in "0123456789abcdef" for c in entry_hash):
        errors.append("checkpoint entry_sha256 must be a lowercase SHA-256 hex digest")
    issued_at = _parse_timestamp(payload.get("issued_at"))
    if issued_at is None:
        errors.append("checkpoint issued_at must be an ISO-8601 timestamp with a timezone")
    else:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            errors.append("verification clock must be timezone-aware")
        else:
            age = (current.astimezone(timezone.utc) - issued_at).total_seconds()
            if age < -300:
                errors.append("checkpoint issued_at is more than five minutes in the future")
            if age > max_age_seconds:
                errors.append("checkpoint is stale")
    if errors:
        return errors

    try:
        key_bytes = trusted_public_key_path.read_bytes()
        public_key = serialization.load_pem_public_key(key_bytes)
    except (OSError, ValueError, TypeError) as exc:
        return [f"trusted public key cannot be loaded: {exc}"]
    if not isinstance(public_key, Ed25519PublicKey):
        return ["trusted public key must be an Ed25519 public key"]
    raw_public = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(raw_public).hexdigest()
    if payload["key_fingerprint"] != fingerprint:
        return ["checkpoint key_fingerprint does not match the out-of-band trusted public key"]
    signature_value = checkpoint.get("signature")
    if not isinstance(signature_value, str):
        return ["checkpoint signature must be base64 text"]
    try:
        signature = base64.b64decode(signature_value, validate=True)
        public_key.verify(signature, canonical_json(payload))
    except (ValueError, TypeError) as exc:
        return [f"checkpoint signature encoding is invalid: {exc}"]
    except Exception:
        return ["checkpoint signature verification failed"]

    entries, chain_errors = load_entries(history_path)
    if chain_errors:
        errors.extend("history: " + error for error in chain_errors)
        return errors
    if expected_history_id is not None and payload["history_id"] != expected_history_id:
        errors.append("checkpoint history_id does not match configured history identifier")
    if type(sequence) is int and sequence > len(entries):
        errors.append("checkpoint is ahead of local history; restore or reconcile history")
    elif type(sequence) is int and sequence >= 1 and sequence <= len(entries):
        if entries[sequence - 1].get("entry_sha256") != entry_hash:
            errors.append("local history does not match the independently signed checkpoint")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", required=True, type=Path, help="local release-history JSONL")
    parser.add_argument("--checkpoint", required=True, type=Path, help="independently obtained signed checkpoint JSON")
    parser.add_argument("--public-key", required=True, type=Path, help="out-of-band trusted Ed25519 public key PEM")
    parser.add_argument("--max-age-seconds", type=int, default=86400)
    parser.add_argument("--minimum-sequence", type=int, default=0, help="persisted high-water mark; prevents accepted rollback")
    parser.add_argument("--history-id", help="expected stable history identifier from trusted configuration")
    args = parser.parse_args()
    errors = verify_checkpoint(
        args.history, args.checkpoint, args.public_key,
        max_age_seconds=args.max_age_seconds,
        minimum_sequence=args.minimum_sequence,
        expected_history_id=args.history_id,
    )
    if errors:
        print("CHECKPOINT INVALID / BLOCKED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("CHECKPOINT SIGNATURE AND LOCAL HISTORY MATCH VERIFIED")
    print("Operational independence depends on out-of-band key provisioning and checkpoint delivery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
