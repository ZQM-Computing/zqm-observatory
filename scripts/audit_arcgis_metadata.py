#!/usr/bin/env python3
"""Audit a saved ArcGIS layer metadata JSON file without requesting feature records.

This tool is deliberately offline: it never makes HTTP requests and never
queries a FeatureServer /query endpoint. A metadata report is not a rights
approval or a data-quality certification.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RIGHTS_STATES = {
    "APPROVED",
    "APPROVED_WITH_CONDITIONS",
    "INTERNAL_ONLY",
    "BLOCKED_PENDING_REVIEW",
    "REJECTED",
}


def audit_metadata(metadata: Any, source_url: str, rights_state: str) -> dict[str, Any]:
    """Return a deterministic metadata-only report from one ArcGIS layer JSON."""
    if not isinstance(metadata, dict):
        raise ValueError("input must be a JSON object")
    if rights_state not in RIGHTS_STATES:
        raise ValueError(f"rights_state must be one of: {', '.join(sorted(RIGHTS_STATES))}")

    fields = metadata.get("fields")
    fields = fields if isinstance(fields, list) else []
    field_names = [
        item.get("name") for item in fields
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    geometry = metadata.get("geometryType")
    spatial_ref = metadata.get("spatialReference")
    if not isinstance(spatial_ref, dict):
        spatial_ref = {}
    description = metadata.get("description")
    copyright_text = metadata.get("copyrightText")
    max_records = metadata.get("maxRecordCount")
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, dict):
        advanced = {}

    warnings: list[str] = []
    if not isinstance(description, str) or not description.strip():
        warnings.append("missing_description")
    if not isinstance(copyright_text, str) or not copyright_text.strip():
        warnings.append("missing_copyright_text")
    if not field_names:
        warnings.append("missing_or_unreadable_fields")
    if not spatial_ref:
        warnings.append("missing_spatial_reference")
    if isinstance(max_records, int) and max_records > 0:
        warnings.append("record_limit_requires_pagination_review")
    if not any(name.lower() in {"globalid", "global_id"} for name in field_names):
        warnings.append("no_global_id_field_observed")
    if rights_state not in {"APPROVED", "APPROVED_WITH_CONDITIONS"}:
        warnings.append("collection_and_publication_not_approved")
    if rights_state == "APPROVED_WITH_CONDITIONS":
        warnings.append("verify_all_approval_conditions_before_use")

    return {
        "report_schema_version": 1,
        "inspection_mode": "saved_layer_metadata_only",
        "source_url": source_url,
        "layer_id": metadata.get("id"),
        "layer_name": metadata.get("name"),
        "display_field": metadata.get("displayField"),
        "geometry_type": geometry,
        "description": description if isinstance(description, str) else None,
        "copyright_text": copyright_text if isinstance(copyright_text, str) else None,
        "spatial_reference": spatial_ref,
        "max_record_count": max_records,
        "supports_pagination": advanced.get("supportsPagination"),
        "field_count": len(field_names),
        "field_names": field_names,
        "rights_state": rights_state,
        "feature_records_requested": False,
        "warnings": warnings,
        "limitations": [
            "No network requests or feature-record queries were made.",
            "Metadata does not establish record accuracy, freshness, reuse rights, access, or field conditions.",
            "A rights state is supplied by the operator and is not independently verified by this tool.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata_json", type=Path, help="path to a previously saved ArcGIS layer metadata JSON file")
    parser.add_argument("--source-url", required=True, help="canonical layer metadata URL represented by the saved file")
    parser.add_argument(
        "--rights-state",
        required=True,
        choices=sorted(RIGHTS_STATES),
        help="documented source-rights decision; this tool does not decide rights",
    )
    parser.add_argument("--output", type=Path, help="optional path for the JSON report (stdout if omitted)")
    args = parser.parse_args(argv)

    try:
        metadata = json.loads(args.metadata_json.read_text(encoding="utf-8"))
        report = audit_metadata(metadata, args.source_url, args.rights_state)
        rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"metadata audit failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
