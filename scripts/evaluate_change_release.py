#!/usr/bin/env python3
"""Evaluate a change report against explicit release-blocking policy rules."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
SEVERITIES = {"info", "low", "medium", "high", "critical"}
def evaluate(report: dict[str, Any], rules: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    allowed = {"block_on_severity", "max_removed", "max_added", "require_run_ids"}
    if not isinstance(rules, dict) or set(rules) - allowed:
        return None, ["release rules must contain only block_on_severity, max_removed, max_added, require_run_ids"]
    blocked = rules.get("block_on_severity", [])
    if not isinstance(blocked, list) or any(not isinstance(x, str) or x not in SEVERITIES for x in blocked):
        return None, ["block_on_severity must be a list of valid severity names"]
    limits = {}
    for key in ("max_removed", "max_added"):
        value = rules.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            return None, [f"{key} must be a non-negative integer when supplied"]
        limits[key] = value
    require_ids = rules.get("require_run_ids", True)
    if not isinstance(require_ids, bool):
        return None, ["require_run_ids must be a boolean"]
    if not isinstance(report, dict) or not isinstance(report.get("summary"), dict) or not isinstance(report.get("changed_features"), list) or not isinstance(report.get("inputs"), dict):
        return None, ["change report is missing inputs, summary, or changed_features"]
    violations = []
    if require_ids:
        for side in ("before", "after"):
            entry = report["inputs"].get(side)
            if not isinstance(entry, dict) or not isinstance(entry.get("run_id"), str) or not entry["run_id"].strip():
                violations.append(f"{side} run_id is required by release policy")
    summary = report["summary"]
    for key in ("removed_count", "added_count"):
        if isinstance(summary.get(key), bool) or not isinstance(summary.get(key), int) or summary[key] < 0:
            return None, [f"summary.{key} must be a non-negative integer"]
    for key, count_key in (("max_removed", "removed_count"), ("max_added", "added_count")):
        if limits[key] is not None and summary[count_key] > limits[key]:
            violations.append(f"{count_key} {summary[count_key]} exceeds {key} {limits[key]}")
    for item in report["changed_features"]:
        if not isinstance(item, dict) or item.get("review_severity") not in SEVERITIES:
            return None, ["each changed feature must be an object with a valid review_severity"]
        if item["review_severity"] in blocked:
            violations.append(f"feature {item.get('id', '<unknown>')!r} has blocking review severity {item['review_severity']}")
    return {"schema_version": 1, "report_type": "change_release_gate", "decision": "blocked" if violations else "eligible_for_human_release_review", "violations": violations, "policy": {"block_on_severity": blocked, "max_removed": limits["max_removed"], "max_added": limits["max_added"], "require_run_ids": require_ids}, "limitations": ["Eligibility is not publication authorization; source-rights, factual, privacy, data-quality, and product-owner reviews remain independent mandatory gates.", "Run IDs are operator-supplied labels; hashes are not digital signatures."]}, []
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--rules-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8")); rules = json.loads(args.rules_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read valid JSON: {exc}", file=sys.stderr); return 1
    result, errors = evaluate(report, rules)
    if errors or result is None:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr); return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Release gate: {result['decision']} ({len(result['violations'])} policy violation(s)).")
    return 2 if result["decision"] == "blocked" else 0
if __name__ == "__main__":
    raise SystemExit(main())
