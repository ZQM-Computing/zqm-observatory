#!/usr/bin/env python3
"""Run the pinned qgis-resources dataset QA CLI on a local synthetic fixture.

This adapter is deliberately offline and read-only with respect to its input.
It does not authorize publication or ingest real-world source records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def validate_report(report: Any, expected_feature_count: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        return ["QA report must be an object using schema_version 1"]
    if report.get("dataset_count") != 1:
        errors.append("QA report must inventory exactly one fixture dataset")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        errors.append("QA report summary must be an object")
        summary = {}
    for key in ("error", "warning", "info", "total"):
        if not isinstance(summary.get(key), int) or isinstance(summary.get(key), bool):
            errors.append(f"QA report summary.{key} must be an integer")
    if summary.get("error") != 0:
        errors.append("QA report contains errors")
    if summary.get("warning") != 0:
        errors.append("QA report contains warnings")
    datasets = report.get("datasets")
    if not isinstance(datasets, list) or len(datasets) != 1 or not isinstance(datasets[0], dict):
        errors.append("QA report datasets must contain exactly one inventory object")
    else:
        dataset = datasets[0]
        if dataset.get("kind") != "vector":
            errors.append("synthetic fixture must be inventoried as vector data")
        layers = dataset.get("layers")
        if not isinstance(layers, list) or not layers:
            errors.append("synthetic vector fixture must contain at least one layer")
        else:
            observed = 0
            for layer in layers:
                if not isinstance(layer, dict):
                    errors.append("each layer inventory must be an object")
                    continue
                count = layer.get("feature_count")
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    errors.append("layer feature_count must be a non-negative integer")
                else:
                    observed += count
                names = layer.get("fields")
                # The upstream CLI's required-field checks are authoritative; this
                # adapter independently checks the reported layer schema when available.
                if isinstance(names, list):
                    field_names = {
                        item.get("name") for item in names if isinstance(item, dict)
                    }
                    if names and not {"id", "name"}.issubset(field_names):
                        errors.append("layer report does not expose required id/name fields")
            if observed != expected_feature_count:
                errors.append(
                    f"observed feature count {observed} does not match fixture count {expected_feature_count}"
                )
    findings = report.get("findings")
    if not isinstance(findings, list):
        errors.append("QA report findings must be a list")
    elif findings:
        errors.append("QA report must have no findings for the controlled synthetic fixture")
    return errors


def load_feature_count(fixture: Path) -> int:
    value = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("type") != "FeatureCollection":
        raise ValueError("fixture must be a GeoJSON FeatureCollection")
    features = value.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("fixture must contain a non-empty features array")
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            raise ValueError(f"feature {index} must contain a properties object")
        for field in ("id", "name"):
            if not isinstance(feature["properties"].get(field), str) or not feature["properties"][field].strip():
                raise ValueError(f"feature {index} requires non-empty string properties.{field}")
    return len(features)


def run_cli(
    python: str, qa_script: Path, fixture: Path, report_path: Path, cwd: Path
) -> tuple[int, list[str]]:
    command = [
        python, str(qa_script), str(fixture),
        "--root", str(fixture.parent),
        "--json", str(report_path),
        "--required-field", "id",
        "--required-field", "name",
        "--id-field", "id",
        "--expected-crs", "EPSG:4326",
        "--fail-on-warning",
    ]
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    errors: list[str] = []
    if result.returncode != 0:
        errors.append(
            f"upstream QA CLI returned {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()}"
        )
    if not report_path.is_file():
        errors.append("upstream QA CLI did not create its JSON report")
    return result.returncode, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-script", type=Path, required=True, help="Path to pinned qgis-resources/scripts/dataset_qa.py")
    parser.add_argument("--fixture", type=Path, required=True, help="Local synthetic GeoJSON FeatureCollection")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for QA reports and handoff manifest")
    parser.add_argument("--producer-commit", required=True, help="Exact qgis-resources commit checked out by CI")
    args = parser.parse_args(argv)

    qa_script = args.qa_script.resolve()
    fixture = args.fixture.resolve()
    output_dir = args.output_dir.resolve()
    if not qa_script.is_file():
        parser.error(f"QA script does not exist: {qa_script}")
    if not fixture.is_file():
        parser.error(f"fixture does not exist: {fixture}")
    if not args.producer_commit or any(ch not in "0123456789abcdef" for ch in args.producer_commit.lower()):
        parser.error("--producer-commit must be a hexadecimal commit identifier")
    if len(args.producer_commit) < 7:
        parser.error("--producer-commit must contain at least 7 hexadecimal characters")
    if output_dir == fixture.parent or fixture in output_dir.parents:
        parser.error("output directory must not be inside the fixture directory")

    try:
        feature_count = load_feature_count(fixture)
        before_hash = sha256_file(fixture)
        output_dir.mkdir(parents=True, exist_ok=True)
        report_a = output_dir / "qa-report-run-a.json"
        report_b = output_dir / "qa-report-run-b.json"
        for path in (report_a, report_b):
            if path.exists():
                path.unlink()
        repo_root = qa_script.parent.parent
        _, errors_a = run_cli(sys.executable, qa_script, fixture, report_a, repo_root)
        _, errors_b = run_cli(sys.executable, qa_script, fixture, report_b, repo_root)
        errors = errors_a + errors_b
        if not errors_a and not errors_b:
            raw_a, raw_b = report_a.read_bytes(), report_b.read_bytes()
            if raw_a != raw_b:
                errors.append("upstream QA report is not byte-for-byte deterministic across identical runs")
            for label, path in (("first", report_a), ("second", report_b)):
                report = json.loads(path.read_text(encoding="utf-8"))
                errors.extend(f"{label} report: {item}" for item in validate_report(report, feature_count))
        after_hash = sha256_file(fixture)
        if before_hash != after_hash:
            errors.append("fixture SHA-256 changed during QA; input must remain read-only")
        if not errors:
            report_hash = sha256_file(report_a)
            manifest = {
                "schema_version": 1,
                "manifest_type": "zqm_observatory_external_qa_handoff",
                "decision": "technical_qa_passed_pending_independent_release_gates",
                "publication_authorized": False,
                "network_access_requested": False,
                "fixture": {
                    "path": fixture.name,
                    "sha256_before": before_hash,
                    "sha256_after": after_hash,
                    "feature_count": feature_count,
                    "synthetic_only": True,
                },
                "producer": {
                    "repository": "ZQM-Computing/qgis-resources",
                    "commit": args.producer_commit.lower(),
                    "script": "scripts/dataset_qa.py",
                    "python": sys.version.split()[0],
                    "gdal": subprocess.run(
                        ["gdal-config", "--version"], capture_output=True, text=True, check=True
                    ).stdout.strip(),
                },
                "invocation": {
                    "required_fields": ["id", "name"],
                    "id_field": "id",
                    "expected_crs": "EPSG:4326",
                    "fail_on_warning": True,
                    "runs": 2,
                },
                "qa_report": {
                    "path": report_a.name,
                    "sha256": report_hash,
                    "byte_identical_second_run": True,
                },
                "guardrails": {
                    "source_rights_approved": False,
                    "privacy_review_approved": False,
                    "human_release_review_completed": False,
                },
            }
            manifest_path = output_dir / "handoff-manifest.json"
            manifest_path.write_bytes(canonical_json(manifest))
            print(f"External QA handoff verified: {manifest_path}")
            print(f"Fixture SHA-256 unchanged: {after_hash}")
            print(f"QA report SHA-256: {report_hash}")
            return 0
        print("\n".join(f"ERROR: {item}" for item in errors), file=sys.stderr)
        return 1
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: QA handoff failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
