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


def extent(features: dict[str, dict[str, Any]]) -> list[float] | None:
    if not features:
        return None
    points = [item["geometry"]["coordinates"] for item in features.values()]
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]


def compare(before_path: Path, after_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
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
        changed_properties = {
            key: {"before": old["properties"].get(key), "after": new["properties"].get(key)}
            for key in sorted(set(old["properties"]) | set(new["properties"]))
            if old["properties"].get(key) != new["properties"].get(key)
        }
        if geometry_changed or changed_properties:
            changed.append({
                "id": feature_id,
                "geometry_changed": geometry_changed,
                "changed_properties": changed_properties,
            })

    before_extent, after_extent = extent(before), extent(after)
    report = {
        "schema_version": 1,
        "report_type": "geojson_feature_change_impact",
        "inputs": {
            "before": {"path": before_path.name, "sha256": sha256_file(before_path)},
            "after": {"path": after_path.name, "sha256": sha256_file(after_path)},
        },
        "summary": {
            "feature_count_before": len(before),
            "feature_count_after": len(after),
            "added_count": len(added_ids),
            "removed_count": len(removed_ids),
            "changed_count": len(changed),
            "unchanged_count": len(before_ids & after_ids) - len(changed),
            "extent_changed": before_extent != after_extent,
        },
        "extent": {"before": before_extent, "after": after_extent},
        "added_ids": added_ids,
        "removed_ids": removed_ids,
        "changed_features": changed,
        "limitations": [
            "Comparison is feature-ID based and supports the pipeline's Point GeoJSON contract only.",
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
    args = parser.parse_args()
    report, errors = compare(args.before, args.after)
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
