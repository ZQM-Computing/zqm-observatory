#!/usr/bin/env python3
"""Create a deterministic change-impact report between two normalized GeoJSON runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.baseline_registry import verify_entry
except ModuleNotFoundError:  # Direct script execution puts scripts/ on sys.path.
    from baseline_registry import verify_entry


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_features(path: Path) -> tuple[dict[str, dict[str, Any]], list[str], str | None]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [], f"cannot read valid UTF-8 JSON: {exc}"
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        return {}, [], "top-level type must be FeatureCollection"
    features = document.get("features")
    if not isinstance(features, list):
        return {}, [], "features must be a list"

    indexed: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, feature in enumerate(features):
        label = f"features[{index}]"
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            errors.append(f"{label}: must be a Feature")
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            errors.append(f"{label}: properties must be an object")
            continue
        feature_id = properties.get("id")
        if not isinstance(feature_id, str) or not feature_id.strip():
            errors.append(f"{label}: properties.id must be a non-empty string")
            continue
        if feature_id in indexed:
            errors.append(f"{label}: duplicate feature id {feature_id!r}")
            continue
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            errors.append(f"{label}: geometry must be a Point")
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) != 2:
            errors.append(f"{label}: Point coordinates must contain exactly longitude and latitude")
            continue
        lon, lat = coordinates
        if (isinstance(lon, bool) or isinstance(lat, bool)
                or not isinstance(lon, (int, float)) or not isinstance(lat, (int, float))
                or not math.isfinite(lon) or not math.isfinite(lat)
                or not (-180 <= lon <= 180 and -90 <= lat <= 90)):
            errors.append(f"{label}: coordinates must be finite WGS84 longitude/latitude")
            continue
        if any(not isinstance(value, str) or not value.strip() for value in
               (properties.get("name"), properties.get("category"))):
            errors.append(f"{label}: properties.name and properties.category must be non-empty strings")
            continue
        indexed[feature_id] = {
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {key: properties[key] for key in ("name", "category")},
        }
    return indexed, errors, None


def distance_meters(left: list[float], right: list[float]) -> float:
    """Great-circle distance between WGS84 lon/lat points (antimeridian-safe)."""
    radius_m = 6_371_008.8
    lon1, lat1 = map(math.radians, left)
    lon2, lat2 = map(math.radians, right)
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def extent(features: dict[str, dict[str, Any]]) -> list[float] | None:
    if not features:
        return None
    points = [item["geometry"]["coordinates"] for item in features.values()]
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]


SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
DEFAULT_REVIEW_RULES: dict[str, Any] = {"default": "low", "geometry": "medium", "properties": {}}


def load_review_rules(path: Path | None) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if path is None:
        return DEFAULT_REVIEW_RULES, None, None
    try:
        raw = path.read_bytes()
        rules = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, None, f"cannot read valid review rules JSON: {exc}"
    if not isinstance(rules, dict) or set(rules) - {"default", "geometry", "properties"}:
        return None, None, "review rules must be an object with only default, geometry, and properties keys"
    rules = {"default": rules.get("default", "low"), "geometry": rules.get("geometry", "medium"), "properties": rules.get("properties", {})}
    if not isinstance(rules["default"], str) or rules["default"] not in SEVERITY_RANK or not isinstance(rules["geometry"], str) or rules["geometry"] not in SEVERITY_RANK:
        return None, None, "default and geometry severities must be info, low, medium, high, or critical"
    if not isinstance(rules["properties"], dict):
        return None, None, "properties rules must be an object mapping property names to severities"
    for key, severity in rules["properties"].items():
        if not isinstance(key, str) or not isinstance(severity, str) or severity not in SEVERITY_RANK:
            return None, None, "each property rule must map a string property name to info, low, medium, high, or critical"
    return rules, hashlib.sha256(raw).hexdigest(), None


def compare(before_path: Path, after_path: Path, movement_threshold_m: float = 0.0, rules_path: Path | None = None, before_id: str | None = None, after_id: str | None = None, registry_path: Path | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    if not math.isfinite(movement_threshold_m) or movement_threshold_m < 0:
        return None, ["movement threshold must be a finite non-negative number"]
    if (before_id is not None and not before_id.strip()) or (after_id is not None and not after_id.strip()):
        return None, ["run identifiers, when supplied, must be non-empty strings"]
    if registry_path is not None:
        if not before_id or not after_id:
            return None, ["--registry requires both --before-id and --after-id"]
        _, registry_errors = verify_entry(registry_path, before_id, before_path)
        if registry_errors:
            return None, [f"baseline registry: {error}" for error in registry_errors]
        _, registry_errors = verify_entry(registry_path, after_id, after_path)
        if registry_errors:
            return None, [f"candidate registry: {error}" for error in registry_errors]
    rules, rules_sha256, rules_error = load_review_rules(rules_path)
    if rules_error or rules is None:
        return None, [rules_error or "review rules are invalid"]
    before, before_errors, before_load_error = load_features(before_path)
    after, after_errors, after_load_error = load_features(after_path)
    errors: list[str] = []
    if before_load_error:
        errors.append(f"before: {before_load_error}")
    errors.extend(f"before: {error}" for error in before_errors)
    if after_load_error:
        errors.append(f"after: {after_load_error}")
    errors.extend(f"after: {error}" for error in after_errors)
    if errors:
        return None, errors

    before_ids, after_ids = set(before), set(after)
    added_ids = sorted(after_ids - before_ids)
    removed_ids = sorted(before_ids - after_ids)
    changed: list[dict[str, Any]] = []
    for feature_id in sorted(before_ids & after_ids):
        old, new = before[feature_id], after[feature_id]
        geometry_changed = old["geometry"] != new["geometry"]
        movement_m = distance_meters(old["geometry"]["coordinates"], new["geometry"]["coordinates"]) if geometry_changed else 0.0
        changed_properties = {
            key: {"before": old["properties"].get(key), "after": new["properties"].get(key)}
            for key in sorted(set(old["properties"]) | set(new["properties"]))
            if old["properties"].get(key) != new["properties"].get(key)
        }
        if geometry_changed or changed_properties:
            severities = [rules["geometry"]] if geometry_changed else []
            severities.extend(rules["properties"].get(key, rules["default"]) for key in changed_properties)
            severity = max(severities, key=lambda item: SEVERITY_RANK[item]) if severities else rules["default"]
            changed.append({
                "id": feature_id,
                "geometry_changed": geometry_changed,
                "movement_meters": round(movement_m, 3) if geometry_changed else None,
                "movement_threshold_meters": movement_threshold_m if geometry_changed else None,
                "movement_exceeds_threshold": movement_m > movement_threshold_m if geometry_changed else False,
                "change_class": ("geometry_moved_above_threshold" if movement_m > movement_threshold_m else "geometry_moved_at_or_below_threshold") if geometry_changed else "attributes_changed",
                "review_severity": severity,
                "changed_properties": changed_properties,
            })

    before_extent, after_extent = extent(before), extent(after)
    report = {
        "schema_version": 1,
        "report_type": "geojson_feature_change_impact",
        "inputs": {
            "before": {"path": before_path.name, "run_id": before_id, "sha256": sha256_file(before_path)},
            "after": {"path": after_path.name, "run_id": after_id, "sha256": sha256_file(after_path)},
        },
        "review_configuration": {"default_severity": rules["default"], "geometry_severity": rules["geometry"], "property_severities": rules["properties"], "rules_sha256": rules_sha256},
        "summary": {
            "feature_count_before": len(before),
            "feature_count_after": len(after),
            "added_count": len(added_ids),
            "removed_count": len(removed_ids),
            "changed_count": len(changed),
            "unchanged_count": len(before_ids & after_ids) - len(changed),
            "extent_changed": before_extent != after_extent,
            "geometry_movement_over_threshold_count": sum(1 for item in changed if item["geometry_changed"] and item["movement_exceeds_threshold"]),
            "movement_threshold_meters": movement_threshold_m,
        },
        "extent": {"before": before_extent, "after": after_extent},
        "added_ids": added_ids,
        "removed_ids": removed_ids,
        "changed_features": changed,
        "limitations": [
            "Comparison is feature-ID based and supports the pipeline's Point GeoJSON contract only.",
            "Movement thresholds are configurable review heuristics, not evidence of real-world significance or positional accuracy.",
            "A change report describes data differences; it does not establish real-world significance, source authority, licensing, privacy approval, or publication permission.",
            "Hashes provide integrity/change-detection signals, not a digital signature."
        ],
    }
    return report, []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path, help="earlier normalized GeoJSON")
    parser.add_argument("--after", required=True, type=Path, help="later normalized GeoJSON")
    parser.add_argument("--output", required=True, type=Path, help="path for the JSON change report")
    parser.add_argument("--movement-threshold-meters", type=float, default=0.0, help="heuristic great-circle movement threshold in meters (default: 0; not a significance or accuracy claim)")
    parser.add_argument("--rules-json", type=Path, help="optional JSON review rules mapping changed fields to review severities")
    parser.add_argument("--before-id", help="explicit immutable/versioned identifier for the baseline run")
    parser.add_argument("--after-id", help="explicit immutable/versioned identifier for the candidate run")
    parser.add_argument("--registry", type=Path, help="content-hash registry used to verify both run IDs against input files")
    args = parser.parse_args()
    report, errors = compare(args.before, args.after, args.movement_threshold_meters, args.rules_json, args.before_id, args.after_id, args.registry)
    if errors or report is None:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json(report))
    print(
        "Change report written: "
        f"{report['summary']['added_count']} added, "
        f"{report['summary']['removed_count']} removed, "
        f"{report['summary']['changed_count']} changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
