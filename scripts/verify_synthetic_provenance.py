#!/usr/bin/env python3
"""Verify a synthetic pipeline run against its recorded SHA-256 provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from strict_json import loads_strict


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(input_path: Path, output_dir: Path, pipeline_script: Path | None = None) -> list[str]:
    """Return integrity failures; an empty list means the recorded files match."""
    errors: list[str] = []
    provenance_path = output_dir / "provenance.json"
    try:
        provenance = loads_strict(provenance_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"provenance.json cannot be read as valid JSON: {exc}"]
    if not isinstance(provenance, dict) or provenance.get("schema_version") != 1:
        return ["provenance schema_version must be 1"]

    def check_hash(label: str, path: Path, expected: object) -> None:
        if not isinstance(expected, str) or len(expected) != 64:
            errors.append(f"{label}: recorded SHA-256 is missing or malformed")
            return
        try:
            actual = sha256_file(path)
        except OSError as exc:
            errors.append(f"{label}: file cannot be read: {exc}")
            return
        if actual != expected:
            errors.append(f"{label}: SHA-256 mismatch")

    input_record = provenance.get("input")
    if not isinstance(input_record, dict):
        errors.append("input provenance record is missing")
    else:
        check_hash("input", input_path, input_record.get("sha256"))

    pipeline_record = provenance.get("pipeline_source")
    if not isinstance(pipeline_record, dict):
        errors.append("pipeline_source provenance record is missing")
    else:
        script_path = pipeline_script or Path(__file__).with_name("build_synthetic_product.py")
        check_hash("pipeline source", script_path, pipeline_record.get("sha256"))

    output_record = provenance.get("output")
    if not isinstance(output_record, dict) or output_record.get("path") != "normalized.geojson":
        errors.append("output provenance must identify normalized.geojson")
    else:
        check_hash("normalized output", output_dir / "normalized.geojson", output_record.get("sha256"))

    qa_record = provenance.get("qa_report")
    if not isinstance(qa_record, dict) or qa_record.get("path") != "qa-report.json":
        errors.append("QA provenance must identify qa-report.json")
    else:
        check_hash("QA report", output_dir / "qa-report.json", qa_record.get("sha256"))
    try:
        qa = loads_strict((output_dir / "qa-report.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"QA report cannot be read as valid JSON: {exc}")
    else:
        if not isinstance(qa, dict) or qa.get("status") != "passed":
            errors.append("QA report status must be passed")
    if provenance.get("publication_authorized") is not False:
        errors.append("synthetic pipeline provenance must keep publication_authorized false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("tests/fixtures/synthetic-places.geojson"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/synthetic-product"))
    parser.add_argument("--pipeline-script", type=Path, default=Path(__file__).with_name("build_synthetic_product.py"))
    args = parser.parse_args()
    errors = verify(args.input, args.output_dir, args.pipeline_script)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("Integrity verified: input, pipeline source, normalized output, and QA report match provenance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
