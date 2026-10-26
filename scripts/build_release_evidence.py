#!/usr/bin/env python3
"""Build a deterministic, hash-linked release evidence manifest; never grants approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from shutil import copyfile
from typing import Any

try:
    from scripts.evaluate_change_release import evaluate
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from evaluate_change_release import evaluate
    from strict_json import loads_strict

try:
    from scripts.baseline_registry import verify_entry
except ModuleNotFoundError:
    from baseline_registry import verify_entry


REVIEW_GATES = ("source_rights", "privacy", "factual_quality", "product_owner")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = loads_strict(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [f"{label} cannot be read as valid JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label} must be a JSON object"]
    return value, []


def validate_non_authorizing_provenance(value: dict[str, Any]) -> list[str]:
    """Release evidence bundles must never carry an authorization-granting provenance record."""
    if value.get("publication_authorized") is not False:
        return [
            "release evidence requires provenance publication_authorized=false; "
            "publication authorization must be handled by a separate, explicit release process"
        ]
    return []


def validate_reviews(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1 or value.get("review_type") != "zqm_observatory_release_reviews":
        errors.append("reviews must use schema_version 1 and review_type zqm_observatory_release_reviews")
    gates = value.get("gates")
    if not isinstance(gates, dict):
        return errors + ["reviews.gates must be an object"]
    unexpected_gates = sorted(set(gates) - set(REVIEW_GATES))
    if unexpected_gates:
        errors.append("reviews.gates contains unexpected gate(s): " + ", ".join(str(name) for name in unexpected_gates))
    for gate in REVIEW_GATES:
        item = gates.get(gate)
        if not isinstance(item, dict):
            errors.append(f"review gate {gate} is missing or not an object")
            continue
        if item.get("decision") != "approved":
            errors.append(f"review gate {gate} is not approved")
        reviewer = item.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer.strip():
            errors.append(f"review gate {gate} requires a non-empty reviewer")
        reviewed_on = item.get("reviewed_on")
        try:
            if not isinstance(reviewed_on, str) or date.fromisoformat(reviewed_on).isoformat() != reviewed_on:
                raise ValueError
        except ValueError:
            errors.append(f"review gate {gate} requires reviewed_on in YYYY-MM-DD format")
        evidence = item.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"review gate {gate} requires an evidence reference")
    return errors


def build_manifest(
    product_dir: Path, before_path: Path, after_path: Path, registry_path: Path,
    change_path: Path, gate_path: Path, reviews_path: Path, policy_path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    provenance, e = read_json(product_dir / "provenance.json", "provenance.json")
    errors.extend(e)
    qa, e = read_json(product_dir / "qa-report.json", "qa-report.json")
    errors.extend(e)
    change, e = read_json(change_path, "change report")
    errors.extend(e)
    gate, e = read_json(gate_path, "release gate report")
    errors.extend(e)
    reviews, e = read_json(reviews_path, "human review record")
    errors.extend(e)
    registry, e = read_json(registry_path, "baseline registry")
    errors.extend(e)
    policy, e = read_json(policy_path, "release policy")
    errors.extend(e)
    if errors:
        return None, errors
    assert provenance is not None and qa is not None and change is not None and gate is not None and reviews is not None and registry is not None and policy is not None

    errors.extend(validate_reviews(reviews))
    if qa.get("status") != "passed":
        errors.append("QA report status must be passed")
    if type(provenance.get("schema_version")) is not int or provenance.get("schema_version") != 1:
        errors.append("provenance schema_version must be 1")
    errors.extend(validate_non_authorizing_provenance(provenance))
    if gate.get("decision") not in ("blocked", "eligible_for_human_release_review"):
        errors.append("release gate decision is missing or unrecognized")
    if change.get("report_type") != "geojson_feature_change_impact" or not isinstance(change.get("inputs"), dict):
        errors.append("change report type or inputs are invalid")
    if not isinstance(registry.get("runs"), list):
        errors.append("baseline registry runs must be a list")

    for label, path, record in (
        ("normalized output", product_dir / "normalized.geojson", provenance.get("output")),
        ("QA report", product_dir / "qa-report.json", provenance.get("qa_report")),
    ):
        if not isinstance(record, dict) or not isinstance(record.get("sha256"), str) or not SHA256.fullmatch(record["sha256"]):
            errors.append(f"provenance {label} hash is missing or malformed")
            continue
        try:
            actual = sha256_file(path)
        except OSError as exc:
            errors.append(f"{label} cannot be read: {exc}")
            continue
        if actual != record["sha256"]:
            errors.append(f"{label} hash does not match provenance")

    input_record = provenance.get("input")
    if not isinstance(input_record, dict) or not isinstance(input_record.get("sha256"), str) or not SHA256.fullmatch(input_record["sha256"]):
        errors.append("provenance input hash is missing or malformed")
    output_record = provenance.get("output")
    if isinstance(output_record, dict) and isinstance(output_record.get("sha256"), str):
        try:
            candidate_hash = sha256_file(after_path)
        except OSError as exc:
            errors.append(f"candidate dataset cannot be read: {exc}")
        else:
            if candidate_hash != output_record["sha256"]:
                errors.append("candidate dataset does not match the product provenance output hash")
            try:
                product_hash = sha256_file(product_dir / "normalized.geojson")
            except OSError as exc:
                errors.append(f"normalized product cannot be read: {exc}")
            else:
                if product_hash != candidate_hash:
                    errors.append("candidate dataset does not match product-dir normalized.geojson")

    input_map = (("before", before_path), ("after", after_path))
    for side, path in input_map:
        entry = change["inputs"].get(side) if isinstance(change.get("inputs"), dict) else None
        if not isinstance(entry, dict):
            errors.append(f"change report {side} input record is missing")
            continue
        try:
            actual = sha256_file(path)
        except OSError as exc:
            errors.append(f"{side} dataset cannot be read: {exc}")
            continue
        if entry.get("sha256") != actual:
            errors.append(f"change report {side} dataset hash does not match supplied file")
        run_id = entry.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            errors.append(f"change report {side} run_id is required for release evidence")
            continue
        registered, registry_errors = verify_entry(registry_path, run_id, path)
        errors.extend(f"{side} registry verification: {message}" for message in registry_errors)
        if registered is not None and registered.get("dataset_sha256") != actual:
            errors.append(f"{side} registry hash does not match dataset")
    if gate.get("decision") == "blocked":
        errors.append("change release gate is blocked")
    recomputed_gate, policy_errors = evaluate(change, policy)
    errors.extend(f"release policy evaluation: {message}" for message in policy_errors)
    if recomputed_gate is not None:
        if gate.get("decision") != recomputed_gate.get("decision"):
            errors.append("release-gate decision does not match recomputed decision")
        if gate.get("policy") != recomputed_gate.get("policy"):
            errors.append("release-gate policy does not match supplied policy")
        if gate.get("violations") != recomputed_gate.get("violations"):
            errors.append("release-gate violations do not match recomputed violations")

    if errors:
        return None, errors

    review_decisions = {name: reviews["gates"][name]["decision"] for name in REVIEW_GATES}
    provenance_authorized = provenance.get("publication_authorized") is True
    # Evidence packaging is never an authorization mechanism. Even a complete
    # review record remains blocked until a separate release process acts.
    decision = "blocked"
    artifacts: dict[str, dict[str, str]] = {}
    paths = {
        "normalized_dataset": product_dir / "normalized.geojson",
        "qa_report": product_dir / "qa-report.json",
        "provenance": product_dir / "provenance.json",
        "before_dataset": before_path,
        "after_dataset": after_path,
        "baseline_registry": registry_path,
        "change_report": change_path,
        "release_gate_report": gate_path,
        "release_policy": policy_path,
        "human_reviews": reviews_path,
    }
    for name, path in paths.items():
        artifacts[name] = {
            "file_name": path.name,
            "sha256": sha256_file(path),
            "bundle_file": f"{name}{path.suffix or '.bin'}",
        }
    manifest = {
        "schema_version": 1,
        "manifest_type": "zqm_observatory_release_evidence",
        "decision": decision,
        "publication_authorized_by_manifest": False,
        "release_gate": {"decision": gate["decision"], "violations": gate.get("violations", [])},
        "review_decisions": review_decisions,
        "provenance_publication_authorized": provenance_authorized,
        "artifacts": artifacts,
        "evidence_format": "self-contained sibling artifacts; verify with scripts/verify_release_evidence.py",
        "run_identity": {
            "before_run_id": change["inputs"]["before"]["run_id"],
            "after_run_id": change["inputs"]["after"]["run_id"],
            "before_dataset_sha256": artifacts["before_dataset"]["sha256"],
            "after_dataset_sha256": artifacts["after_dataset"]["sha256"],
        },
        "limitations": [
            "This manifest is deterministic evidence packaging, not a digital signature or tamper-proof ledger.",
            "The manifest itself never grants publication authorization; an authorized provenance record and all four explicit human approvals are required.",
            "Human approval records are assertions with evidence references; reviewers must independently inspect the cited evidence and preserve records under access control.",
        ],
    }
    return manifest, []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-dir", required=True, type=Path)
    parser.add_argument("--before-dataset", required=True, type=Path)
    parser.add_argument("--after-dataset", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--change-report", required=True, type=Path)
    parser.add_argument("--release-gate", required=True, type=Path)
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--release-policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest, errors = build_manifest(args.product_dir, args.before_dataset, args.after_dataset, args.registry, args.change_report, args.release_gate, args.reviews, args.release_policy)
    if errors or manifest is None:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "normalized_dataset": args.product_dir / "normalized.geojson",
        "qa_report": args.product_dir / "qa-report.json",
        "provenance": args.product_dir / "provenance.json",
        "before_dataset": args.before_dataset,
        "after_dataset": args.after_dataset,
        "baseline_registry": args.registry,
        "change_report": args.change_report,
        "release_gate_report": args.release_gate,
        "release_policy": args.release_policy,
        "human_reviews": args.reviews,
    }
    for name, source in paths.items():
        destination = args.output.parent / manifest["artifacts"][name]["bundle_file"]
        if source.resolve() != destination.resolve():
            copyfile(source, destination)
        if sha256_file(destination) != manifest["artifacts"][name]["sha256"]:
            print(f"ERROR: copied artifact hash mismatch: {name}", file=sys.stderr)
            return 1
    args.output.write_bytes(canonical_json(manifest))
    print(f"Release evidence: {manifest['decision']}; manifest does not itself authorize publication.")
    return 0 if manifest["decision"] == "release_authorized" else 2


if __name__ == "__main__":
    raise SystemExit(main())
