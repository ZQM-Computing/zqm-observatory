#!/usr/bin/env python3
"""Maintain a hash-linked JSONL history of signed release-evidence attestations."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from strict_json import loads_strict

GENESIS = "0" * 64


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_entries(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], []
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
        record = {key: entry.get(key) for key in ("sequence", "previous_entry_sha256", "attestation_file", "attestation_sha256", "entry_sha256")}
        expected = sha256_bytes(canonical_json({key: value for key, value in record.items() if key != "entry_sha256"}))
        if record["sequence"] != number:
            errors.append(f"line {number}: sequence must be {number}")
        if record["previous_entry_sha256"] != previous:
            errors.append(f"line {number}: previous-entry hash does not match chain")
        if record["entry_sha256"] != expected:
            errors.append(f"line {number}: entry hash mismatch")
        attestation_file = record["attestation_file"]
        if not isinstance(attestation_file, str) or not attestation_file or Path(attestation_file).name != attestation_file:
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


def append_entry(history_path: Path, attestation_path: Path) -> list[str]:
    entries, errors = load_entries(history_path)
    if errors:
        return errors
    try:
        attestation_bytes = attestation_path.read_bytes()
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
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Appended history entry {entry['sequence']} ({entry['entry_sha256']}). Keep history and attestations under controlled/immutable storage.")
    return []


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
            path = root / entry["attestation_file"]
            try:
                actual = sha256_bytes(path.read_bytes())
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
