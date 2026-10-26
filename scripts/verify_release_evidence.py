#!/usr/bin/env python3
"""Independently verify a release-evidence bundle's artifact hashes and policy decision."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.evaluate_change_release import evaluate
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from evaluate_change_release import evaluate
    from strict_json import loads_strict


REQUIRED_ARTIFACTS = {
    "normalized_dataset", "qa_report", "provenance", "before_dataset",
    "after_dataset", "baseline_registry", "change_report",
    "release_gate_report", "release_policy", "human_reviews",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> tuple[Any | None, list[str]]:
    try:
        return loads_strict(path.read_text(encoding="utf-8")), []
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [f"{label} cannot be read as valid JSON: {exc}"]


def verify_manifest(manifest_path: Path) -> list[str]:
    manifest, errors = read_json(manifest_path, "manifest")
    if errors:
        return errors
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("manifest_type") != "zqm_observatory_release_evidence":
        return ["manifest schema or manifest_type is invalid"]
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["manifest.artifacts must be an object"]
    if set(artifacts) != REQUIRED_ARTIFACTS:
        errors.append("manifest artifact roles do not match the required evidence set")
    verified: dict[str, Path] = {}
    for role in sorted(REQUIRED_ARTIFACTS):
        item = artifacts.get(role)
        if not isinstance(item, dict):
            errors.append(f"artifact {role} is missing or invalid")
            continue
        bundle_file, expected = item.get("bundle_file"), item.get("sha256")
        if not isinstance(bundle_file, str) or not bundle_file or Path(bundle_file).name != bundle_file or bundle_file in (".", ".."):
            errors.append(f"artifact {role} has unsafe bundle_file")
            continue
        if not isinstance(expected, str) or len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            errors.append(f"artifact {role} has malformed SHA-256")
            continue
        path = manifest_path.parent / bundle_file
        # Evidence artifacts must be actual files in the bundle, not links to
        # mutable or external files that happen to hash correctly at review time.
        if path.is_symlink():
            errors.append(f"artifact {role} must not be a symlink")
            continue
        try:
            resolved_path = path.resolve(strict=True)
            bundle_root = manifest_path.parent.resolve(strict=True)
        except OSError as exc:
            errors.append(f"artifact {role} missing/unreadable: {exc}")
            continue
        if not resolved_path.is_relative_to(bundle_root) or not resolved_path.is_file():
            errors.append(f"artifact {role} must resolve to a regular file inside the evidence bundle")
            continue
        try:
            actual = sha256_file(resolved_path)
        except OSError as exc:
            errors.append(f"artifact {role} missing/unreadable: {exc}")
            continue
        if actual != expected:
            errors.append(f"artifact {role} SHA-256 mismatch")
            continue
        verified[role] = path

    if errors:
        return errors
    change, e = read_json(verified["change_report"], "change report"); errors.extend(e)
    gate, e = read_json(verified["release_gate_report"], "release gate report"); errors.extend(e)
    policy, e = read_json(verified["release_policy"], "release policy"); errors.extend(e)
    provenance, e = read_json(verified["provenance"], "provenance"); errors.extend(e)
    qa, e = read_json(verified["qa_report"], "QA report"); errors.extend(e)
    reviews, e = read_json(verified["human_reviews"], "human reviews"); errors.extend(e)
    if errors:
        return errors
    if not isinstance(change, dict) or not isinstance(gate, dict) or not isinstance(policy, dict):
        return ["change report, release gate, and policy must be JSON objects"]
    recomputed, policy_errors = evaluate(change, policy)
    errors.extend(f"policy evaluation: {message}" for message in policy_errors)
    if recomputed is None:
        return errors or ["cannot recompute release gate"]
    if gate.get("decision") != recomputed.get("decision"):
        errors.append("release-gate decision does not match recomputed policy decision")
    if gate.get("policy") != recomputed.get("policy"):
        errors.append("release-gate policy does not match bundled policy")
    if gate.get("violations") != recomputed.get("violations"):
        errors.append("release-gate violations do not match recomputed policy result")
    for role, side in (("before_dataset", "before"), ("after_dataset", "after")):
        record = change.get("inputs", {}).get(side) if isinstance(change.get("inputs"), dict) else None
        if not isinstance(record, dict) or record.get("sha256") != artifacts[role].get("sha256"):
            errors.append(f"change report {side} hash does not match bundled dataset")
    if isinstance(qa, dict) and qa.get("status") != "passed":
        errors.append("QA report status is not passed")
    if not isinstance(provenance, dict) or provenance.get("publication_authorized") is not False:
        errors.append("this verifier accepts only explicitly non-authorizing provenance; inspect any other authorization path separately")
    if not isinstance(reviews, dict) or reviews.get("review_type") != "zqm_observatory_release_reviews":
        errors.append("human review record type is invalid")
    if manifest.get("publication_authorized_by_manifest") is not False:
        errors.append("manifest must never claim publication authorization")
    if manifest.get("decision") != "blocked":
        errors.append("verifier cannot grant release authorization; manifest decision must remain blocked pending an external authorized release process")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    errors = verify_manifest(args.manifest)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("Evidence bundle verified: artifact hashes and release-policy decision are consistent; no publication authorization is granted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
