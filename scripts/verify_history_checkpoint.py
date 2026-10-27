#!/usr/bin/env python3
"""Verify an independently sourced, Ed25519-signed release-history checkpoint.

This verifies a checkpoint; it does not fetch one or establish that its source is
independent. The trusted public key must be provisioned out-of-band.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None
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



STATE_SCHEMA_VERSION = 1


@contextlib.contextmanager
def _state_lock(state_path: Path):
    """Serialize state read/verify/write; keep the sidecar lock inode persistent."""
    lock_path = state_path.with_name(state_path.name + ".lock")
    if state_path.is_symlink() or lock_path.is_symlink():
        raise OSError("state and state lock paths must not be symlinks")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(lock_path, flags, 0o600)
    try:
        if not os.path.isfile(lock_path):
            raise OSError("state lock path must be a regular file")
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        elif msvcrt is not None:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\\0")
                os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover
            raise OSError("no supported inter-process state-locking backend")
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            elif msvcrt is not None:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)


def verify_and_update_state(
    history_path: Path,
    checkpoint_path: Path,
    trusted_public_key_path: Path,
    state_path: Path,
    *,
    max_age_seconds: int = 86400,
    now: datetime | None = None,
    expected_history_id: str | None = None,
) -> list[str]:
    """Verify a checkpoint and monotonically persist its accepted high-water mark.

    State durability/independence is deployment-dependent. Protect this file and
    its backups separately from writable history; a local file alone is not an
    independent anchor against an administrator able to replace both.
    """
    try:
        with _state_lock(state_path):
            prior: dict[str, Any] | None = None
            if state_path.exists():
                prior, state_errors = _read_json(state_path, "rollback state")
                if state_errors:
                    return state_errors
                if prior is None or set(prior) != {
                    "schema_version", "history_id", "sequence", "entry_sha256",
                    "issued_at", "key_fingerprint",
                }:
                    return ["rollback state schema is invalid; recover from a separately trusted copy"]
                if type(prior.get("schema_version")) is not int or prior["schema_version"] != STATE_SCHEMA_VERSION:
                    return ["rollback state schema_version is unsupported"]
                if type(prior.get("sequence")) is not int or prior["sequence"] < 1:
                    return ["rollback state sequence is invalid"]
                if _parse_timestamp(prior.get("issued_at")) is None:
                    return ["rollback state issued_at is invalid"]
                for field in ("history_id", "entry_sha256", "key_fingerprint"):
                    if not isinstance(prior.get(field), str) or not prior[field]:
                        return [f"rollback state {field} is invalid"]
            checkpoint, read_errors = _read_json(checkpoint_path, "checkpoint")
            if read_errors or checkpoint is None:
                return read_errors or ["checkpoint could not be read"]
            payload = checkpoint.get("payload")
            if not isinstance(payload, dict):
                return ["checkpoint payload is invalid"]
            minimum_sequence = prior["sequence"] if prior else 0
            errors = verify_checkpoint(
                history_path, checkpoint_path, trusted_public_key_path,
                max_age_seconds=max_age_seconds, now=now,
                minimum_sequence=minimum_sequence,
                expected_history_id=expected_history_id or (prior.get("history_id") if prior else None),
            )
            if errors:
                return errors
            current = {
                "schema_version": STATE_SCHEMA_VERSION,
                "history_id": payload["history_id"],
                "sequence": payload["sequence"],
                "entry_sha256": payload["entry_sha256"],
                "issued_at": payload["issued_at"],
                "key_fingerprint": payload["key_fingerprint"],
            }
            if prior:
                if current["history_id"] != prior["history_id"]:
                    return ["checkpoint history_id changed from persisted rollback state"]
                if current["key_fingerprint"] != prior["key_fingerprint"]:
                    return ["checkpoint signing key changed; explicit trusted key-rotation procedure required"]
                if _parse_timestamp(current["issued_at"]) < _parse_timestamp(prior["issued_at"]):
                    return ["checkpoint issuance timestamp regressed from persisted rollback state"]
                if current["sequence"] == prior["sequence"]:
                    if current["entry_sha256"] != prior["entry_sha256"]:
                        return ["same-sequence checkpoint conflicts with persisted rollback state"]
            temp_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", newline="\\n", dir=state_path.parent,
                    prefix=f".{state_path.name}.", suffix=".tmp", delete=False,
                ) as stream:
                    temp_name = stream.name
                    json.dump(current, stream, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                    stream.write("\\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_name, state_path)
                temp_name = None
            finally:
                if temp_name is not None:
                    try:
                        os.unlink(temp_name)
                    except OSError:
                        pass
            return []
    except OSError as exc:
        return [f"rollback state lock/update failed: {exc}"]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", required=True, type=Path, help="local release-history JSONL")
    parser.add_argument("--checkpoint", required=True, type=Path, help="independently obtained signed checkpoint JSON")
    parser.add_argument("--public-key", required=True, type=Path, help="out-of-band trusted Ed25519 public key PEM")
    parser.add_argument("--max-age-seconds", type=int, default=86400)
    parser.add_argument("--minimum-sequence", type=int, default=0, help="externally persisted high-water sequence; prevents accepted rollback")
    parser.add_argument("--state-file", type=Path, help="atomically persist the accepted high-water mark; protect this file independently")
    parser.add_argument("--history-id", help="expected stable history identifier from trusted configuration")
    args = parser.parse_args()
    if args.state_file:
        errors = verify_and_update_state(
            args.history, args.checkpoint, args.public_key, args.state_file,
            max_age_seconds=args.max_age_seconds,
            expected_history_id=args.history_id,
        )
    else:
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
    if args.state_file:
        print("Accepted checkpoint high-water mark persisted under the state-file lock.")
        print("Protect the state file and backups in a separate trust domain; local state alone is not an external anchor.")
    else:
        print("Operational independence depends on out-of-band key provisioning and checkpoint delivery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
