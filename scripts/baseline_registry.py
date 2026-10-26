#!/usr/bin/env python3
"""Maintain a content-hash registry of geospatial data runs."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from typing import Any
try:
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from strict_json import loads_strict
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()
def load_registry(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists(): return {"schema_version": 1, "registry_type": "zqm_observatory_baseline_registry", "runs": []}, []
    try: value = loads_strict(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc: return None, [f"cannot read registry JSON: {exc}"]
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1 or value.get("registry_type") != "zqm_observatory_baseline_registry" or not isinstance(value.get("runs"), list):
        return None, ["registry must use schema_version 1 and contain a runs list"]
    seen = set()
    for i, run in enumerate(value["runs"]):
        if not isinstance(run, dict): return None, [f"runs[{i}] must be an object"]
        rid = run.get("run_id")
        if not isinstance(rid, str) or not RUN_ID.fullmatch(rid) or rid in seen: return None, [f"runs[{i}] has invalid or duplicate run_id"]
        seen.add(rid)
        if not isinstance(run.get("dataset_sha256"), str) or not SHA256.fullmatch(run["dataset_sha256"]): return None, [f"runs[{i}] has invalid dataset_sha256"]
        if not isinstance(run.get("pipeline_version"), str) or not run["pipeline_version"].strip(): return None, [f"runs[{i}] requires pipeline_version"]
        if not isinstance(run.get("description"), str) or not run["description"].strip(): return None, [f"runs[{i}] requires description"]
    return value, []
def verify_entry(registry_path: Path, run_id: str, dataset_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    registry, errors = load_registry(registry_path)
    if errors or registry is None: return None, errors
    matches = [r for r in registry["runs"] if r["run_id"] == run_id]
    if not matches: return None, [f"run_id {run_id!r} is not registered"]
    try: actual = sha256_file(dataset_path)
    except OSError as exc: return None, [f"dataset cannot be read: {exc}"]
    entry = matches[0]
    if actual != entry["dataset_sha256"]: return None, [f"dataset hash mismatch for {run_id!r}: registry={entry['dataset_sha256']} actual={actual}"]
    return entry, []
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register")
    for p in (reg,):
        p.add_argument("--registry", required=True, type=Path); p.add_argument("--run-id", required=True); p.add_argument("--dataset", required=True, type=Path)
    reg.add_argument("--pipeline-version", required=True); reg.add_argument("--description", required=True)
    ver = sub.add_parser("verify")
    ver.add_argument("--registry", required=True, type=Path); ver.add_argument("--run-id", required=True); ver.add_argument("--dataset", required=True, type=Path)
    args = parser.parse_args()
    if not RUN_ID.fullmatch(args.run_id):
        print("ERROR: run_id must be 1-128 safe ASCII letters, digits, dots, underscores, colons, or hyphens", file=sys.stderr); return 1
    registry, errors = load_registry(args.registry)
    if errors or registry is None:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr); return 1
    if args.command == "register":
        if any(r["run_id"] == args.run_id for r in registry["runs"]):
            print(f"ERROR: run_id {args.run_id!r} already exists; registry entries cannot be overwritten", file=sys.stderr); return 1
        if not args.pipeline_version.strip() or not args.description.strip():
            print("ERROR: pipeline version and description must be non-empty", file=sys.stderr); return 1
        try: digest = sha256_file(args.dataset)
        except OSError as exc: print(f"ERROR: dataset cannot be read: {exc}", file=sys.stderr); return 1
        registry["runs"].append({"run_id": args.run_id, "dataset_sha256": digest, "pipeline_version": args.pipeline_version.strip(), "description": args.description.strip()})
        args.registry.parent.mkdir(parents=True, exist_ok=True)
        args.registry.write_text(json.dumps(registry, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(f"Registered {args.run_id}: sha256:{digest}"); return 0
    entry, errors = verify_entry(args.registry, args.run_id, args.dataset)
    if errors or entry is None:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr); return 1
    print(f"Verified {args.run_id}: sha256:{entry['dataset_sha256']}"); return 0
if __name__ == "__main__": raise SystemExit(main())
