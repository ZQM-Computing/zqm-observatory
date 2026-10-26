#!/usr/bin/env python3
"""Fail-closed validator for Observatory source rights decisions.

This validates the rights register's structure and conservative decision rules.
It does not interpret licenses or provide legal advice.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from strict_json import loads_strict
from typing import Any
from urllib.parse import urlparse

DECISIONS = {"APPROVED", "APPROVED_WITH_CONDITIONS", "INTERNAL_ONLY", "BLOCKED_PENDING_REVIEW", "REJECTED"}
USES = {"automated_capture", "transformation", "spatial_join", "public_display", "raw_redistribution", "derived_redistribution"}
PUBLIC_USES = {"public_display", "raw_redistribution", "derived_redistribution"}
REQUIRED_SOURCE = {
    "id", "title", "publisher", "service_url", "intended_product", "decision",
    "terms_url", "terms_evidence", "reviewed_at", "reviewer", "permitted_uses",
    "required_attribution", "unresolved_questions", "metadata_review_only",
}


def iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def https_url(value: Any) -> bool:
    if not isinstance(value, str) or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None and (parsed.port is None or 1 <= parsed.port <= 65535)
    except ValueError:
        return False


def validate_document(document: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["root must be a JSON object"]
    if document.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    policy = document.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        if policy.get("default_decision") != "BLOCKED_PENDING_REVIEW":
            errors.append("policy.default_decision must fail closed")
        if policy.get("publication_requires_explicit_approval") is not True:
            errors.append("policy.publication_requires_explicit_approval must be true")
    sources = document.get("sources")
    if not isinstance(sources, list) or not sources:
        return errors + ["sources must be a non-empty array"]

    seen: set[str] = set()
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = sorted(REQUIRED_SOURCE - source.keys())
        if missing:
            errors.append(f"{label} missing fields: {', '.join(missing)}")
            continue
        source_id = source["id"]
        if not isinstance(source_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id):
            errors.append(f"{label}.id must be a unique lowercase kebab-case identifier")
        elif source_id in seen:
            errors.append(f"{label}.id duplicates {source_id!r}")
        else:
            seen.add(source_id)
        for field in ("title", "publisher", "intended_product", "reviewer"):
            if not isinstance(source[field], str) or not source[field].strip():
                errors.append(f"{label}.{field} must be a non-empty string")
        if not https_url(source["service_url"]):
            errors.append(f"{label}.service_url must be a valid HTTPS URL")
        if source["terms_url"] is not None and not https_url(source["terms_url"]):
            errors.append(f"{label}.terms_url must be null or a valid HTTPS URL")
        if not iso_date(source["reviewed_at"]):
            errors.append(f"{label}.reviewed_at must be an ISO date")

        decision = source["decision"]
        if not isinstance(decision, str) or decision not in DECISIONS:
            errors.append(f"{label}.decision is not an allowed decision")
            decision = None

        uses = source["permitted_uses"]
        if not isinstance(uses, dict) or set(uses) != USES:
            errors.append(f"{label}.permitted_uses must define exactly: {', '.join(sorted(USES))}")
            uses = {}
        else:
            for use, value in uses.items():
                if value is not True and value is not False and value is not None:
                    errors.append(f"{label}.permitted_uses.{use} must be true, false, or null")

        evidence = source["terms_evidence"]
        if not isinstance(evidence, list) or any(not isinstance(item, str) or not item.strip() for item in evidence):
            errors.append(f"{label}.terms_evidence must be an array of non-empty evidence references")
            evidence = []

        if decision in {"APPROVED", "APPROVED_WITH_CONDITIONS", "INTERNAL_ONLY"}:
            if not source["terms_url"] or not evidence:
                errors.append(f"{label}: {decision} requires a terms_url and retained terms_evidence")
            if not isinstance(source["required_attribution"], str) or not source["required_attribution"].strip():
                errors.append(f"{label}: approved decision requires explicit required_attribution (use 'None stated' only if evidenced)")
            if not isinstance(source["unresolved_questions"], list) or source["unresolved_questions"]:
                errors.append(f"{label}: approved decision cannot retain unresolved_questions")
            if decision == "APPROVED" and any(uses.get(use) is not True for use in USES):
                errors.append(f"{label}: APPROVED requires explicit true for every use; unknown is not permission")
            if decision == "APPROVED_WITH_CONDITIONS" and not any(uses.get(use) is True for use in USES):
                errors.append(f"{label}: conditional approval must identify at least one explicitly permitted use")
            if decision == "INTERNAL_ONLY" and any(uses.get(use) is True for use in PUBLIC_USES):
                errors.append(f"{label}: INTERNAL_ONLY cannot permit public display or redistribution")
        if decision == "BLOCKED_PENDING_REVIEW" and (not isinstance(source["unresolved_questions"], list) or not source["unresolved_questions"]):
            errors.append(f"{label}: blocked source must state unresolved questions")
        if decision == "REJECTED" and (not isinstance(source["unresolved_questions"], list) or not source["unresolved_questions"]):
            errors.append(f"{label}: rejected source must document why it was rejected")
        if source["metadata_review_only"] is not True and decision in {"BLOCKED_PENDING_REVIEW", "REJECTED"}:
            errors.append(f"{label}: blocked/rejected source must remain marked metadata_review_only until evidence review")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("config/source-rights.json"))
    args = parser.parse_args()
    try:
        document = loads_strict(args.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    errors = validate_document(document)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Source rights validation failed: {len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Source rights register valid: {len(document['sources'])} source decisions; publication remains subject to the recorded decisions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
