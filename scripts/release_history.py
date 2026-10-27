#!/usr/bin/env python3
"""Maintain a hash-linked JSONL history of signed release-evidence attestations."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from strict_json import loads_strict


try:
    import fcntl
except ImportError:  # pragma: no cover - exercised on Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX
    msvcrt = None

GENESIS = "0" * 64


def _is_safe_attestation_filename(value: object) -> bool:
    """Accept a single filename, never a path or traversal component."""
    return (
        isinstance(value, str)
        and value not in {"", ".", ".."}
        and "/" not in value
        and "\\" not in value
        and Path(value).name == value
    )


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_entries(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if path.is_symlink():
        return [], ["history file must not be a symlink"]
    if not path.exists():
        return [], []
    if not path.is_file():
        return [], ["history path must be a regular file"]
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], [f"history cannot be read: {exc}"]
    previous = GENESIS
    seen: set[str] = set()
    for number, line in enumerate(lines, 1):
        try:
            entry = loads_strict(line)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"line {number}: invalid JSON: {exc}")
            continue
        if not isinstance(entry, dict):
            errors.append(f"line {number}: entry must be a JSON object")
            continue
        required_fields = {"sequence", "previous_entry_sha256", "attestation_file", "attestation_sha256", "entry_sha256"}
        if set(entry) != required_fields:
            errors.append(f"line {number}: entry fields do not match the required schema")
        record = {key: entry.get(key) for key in required_fields}
        expected = sha256_bytes(canonical_json({key: value for key, value in record.items() if key != "entry_sha256"}))
        if type(record["sequence"]) is not int or record["sequence"] != number:
            errors.append(f"line {number}: sequence must be integer {number}")
        previous_hash = record["previous_entry_sha256"]
        if not isinstance(previous_hash, str) or len(previous_hash) != 64 or any(ch not in "0123456789abcdef" for ch in previous_hash):
            errors.append(f"line {number}: malformed previous-entry hash")
        if previous_hash != previous:
            errors.append(f"line {number}: previous-entry hash does not match chain")
        entry_hash = record["entry_sha256"]
        if not isinstance(entry_hash, str) or len(entry_hash) != 64 or any(ch not in "0123456789abcdef" for ch in entry_hash):
            errors.append(f"line {number}: malformed entry hash")
        if entry_hash != expected:
            errors.append(f"line {number}: entry hash mismatch")
        attestation_file = record["attestation_file"]
        if not _is_safe_attestation_filename(attestation_file):
            errors.append(f"line {number}: unsafe attestation_file")
        att_hash = record["attestation_sha256"]
        if not isinstance(att_hash, str) or len(att_hash) != 64 or any(ch not in "0123456789abcdef" for ch in att_hash):
            errors.append(f"line {number}: malformed attestation hash")
        if isinstance(att_hash, str) and att_hash in seen:
            errors.append(f"line {number}: attestation is already recorded")
        if isinstance(att_hash, str):
            seen.add(att_hash)
        previous = record["entry_sha256"] if isinstance(record["entry_sha256"], str) else previous
        entries.append(record)
    return entries, errors


def _append_entry_locked(history_path: Path, attestation_path: Path) -> list[str]:
    if history_path.is_symlink():
        return ["history file must not be a symlink"]
    if history_path.exists() and not history_path.is_file():
        return ["history path must be a regular file"]
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [f"history directory cannot be created: {exc}"]

    entries, errors = load_entries(history_path)
    if errors:
        return errors
    # History stores only a basename, so the referenced attestation must live
    # beside the history file. Reject symlinks to prevent reading outside it.
    if attestation_path.is_symlink():
        return ["attestation must not be a symlink"]
    try:
        resolved_attestation = attestation_path.resolve(strict=True)
        resolved_history_dir = history_path.parent.resolve(strict=True)
        if not resolved_attestation.is_file():
            return ["attestation must be a regular file"]
        if resolved_attestation.parent != resolved_history_dir:
            return ["attestation must be in the history directory"]
        attestation_bytes = resolved_attestation.read_bytes()
    except OSError as exc:
        return [f"attestation cannot be read: {exc}"]
    attestation_hash = sha256_bytes(attestation_bytes)
    if any(entry.get("attestation_sha256") == attestation_hash for entry in entries):
        return ["attestation already exists in history"]
    previous = entries[-1]["entry_sha256"] if entries else GENESIS
    body = {
        "sequence": len(entries) + 1,
        "previous_entry_sha256": previous,
        "attestation_file": attestation_path.name,
        "attestation_sha256": attestation_hash,
    }
    entry = {**body, "entry_sha256": sha256_bytes(canonical_json(body))}
    # Atomically replace the complete JSONL file to avoid a partial final line
    # if the process is interrupted while writing. Temp and destination share a
    # directory so os.replace remains on one filesystem.
    line = json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    temp_name: str | None = None
    try:
        existing = history_path.read_bytes() if history_path.exists() else b""
        # A valid final JSON object may exist without a trailing newline. Insert
        # the JSONL record separator before adding the next entry so records
        # never become concatenated into one invalid line.
        if existing and not existing.endswith(b"\n"):
            existing += b"\n"
        with tempfile.NamedTemporaryFile("wb", dir=history_path.parent, prefix=f".{history_path.name}.", suffix=".tmp", delete=False) as stream:
            temp_name = stream.name
            stream.write(existing)
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, history_path)
        temp_name = None
    except OSError as exc:
        return [f"history update failed: {exc}"]
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
    print(f"Appended history entry {entry['sequence']} ({entry['entry_sha256']}). Keep history and attestations under controlled/immutable storage.")
    return []

def append_entry(history_path: Path, attestation_path: Path) -> list[str]:
    """Append one entry while holding an inter-process lock for the full update."""
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with _history_lock(history_path):
            return _append_entry_locked(history_path, attestation_path)
    except OSError as exc:
        return [f"history lock/update failed: {exc}"]



@contextlib.contextmanager
def _history_lock(history_path: Path):
    """Serialize history updates across processes on POSIX and Windows.

    The sidecar lock file is intentionally persistent: unlinking a lock file
    while another process has it open can split writers across different inodes.
    """
    lock_path = history_path.with_name(history_path.name + ".lock")
    if lock_path.is_symlink():
        raise OSError("history lock file must not be a symlink")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(lock_path, flags, 0o600)
    try:
        if not os.path.isfile(lock_path):
            raise OSError("history lock path must be a regular file")
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        elif msvcrt is not None:
            # msvcrt locks a byte range; ensure byte zero exists before locking.
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\\0")
                os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - unsupported runtime
            raise OSError("no supported inter-process file-locking backend")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("append", help="append an attestation to a hash-linked history")
    add.add_argument("--history", required=True, type=Path)
    add.add_argument("--attestation", required=True, type=Path)
    check = sub.add_parser("verify", help="verify history chain and each referenced attestation file hash")
    check.add_argument("--history", required=True, type=Path)
    check.add_argument("--attestation-dir", type=Path, help="directory holding the attestation files; defaults to history directory")
    args = parser.parse_args()
    if args.command == "append":
        errors = append_entry(args.history, args.attestation)
    else:
        entries, errors = load_entries(args.history)
        root = args.attestation_dir or args.history.parent
        for entry in entries:
            filename = entry.get("attestation_file")
            # load_entries has already recorded this as an error; never let malformed
            # data trigger a TypeError or escape the configured attestation directory.
            if not _is_safe_attestation_filename(filename):
                continue
            path = root / filename
            if path.is_symlink():
                errors.append(f"entry {entry['sequence']}: attestation must not be a symlink")
                continue
            try:
                resolved_root = root.resolve(strict=True)
                resolved_path = path.resolve(strict=True)
                if not resolved_path.is_relative_to(resolved_root) or not resolved_path.is_file():
                    errors.append(f"entry {entry['sequence']}: attestation must be a regular file inside the attestation directory")
                    continue
                actual = sha256_bytes(resolved_path.read_bytes())
            except OSError as exc:
                errors.append(f"entry {entry['sequence']}: attestation missing/unreadable: {exc}")
                continue
            if actual != entry["attestation_sha256"]:
                errors.append(f"entry {entry['sequence']}: attestation hash mismatch")
        if not errors:
            print(f"Release history verified: {len(entries)} chained entries. This is not tamper-proof without an external anchor.")
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
