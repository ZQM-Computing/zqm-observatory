#!/usr/bin/env python3
"""Build a deterministic, rights-safe demonstration product from GeoJSON.

This starter pipeline is intentionally offline and fixture-oriented. It does not
fetch real sources or certify a product for publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

PIPELINE_VERSION = "0.1.0"
REQUIRED_PROPERTIES = {"id", "name", "category"}
DEMO_PRODUCT_ID = "2026-10-25-synthetic-geospatial-demo"


def canonical_json(value: Any) -> bytes:
    """Serialize JSON deterministically for stable hashes and diffs."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_geojson(path: Path) -> tuple[dict[str, Any] | None, bytes, list[str]]:
    errors: list[str] = []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, b"", [f"input cannot be read: {exc}"]
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        return None, raw, [f"input is not valid UTF-8 GeoJSON JSON: {exc}"]
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        errors.append("top-level GeoJSON type must be FeatureCollection")
    elif not isinstance(document.get("features"), list):
        errors.append("FeatureCollection.features must be a list")
    return (document if isinstance(document, dict) else None), raw, errors


def normalize(document: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any], list[str]]:
    errors: list[str] = []
    features = document.get("features")
    if not isinstance(features, list):
        return None, {"feature_count": 0}, ["features must be a list"]

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    coordinates: list[tuple[float, float]] = []
    for index, feature in enumerate(features):
        label = f"features[{index}]"
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            errors.append(f"{label}: must be a GeoJSON Feature")
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            errors.append(f"{label}: properties must be an object")
            continue
        missing = sorted(REQUIRED_PROPERTIES - properties.keys())
        if missing:
            errors.append(f"{label}: missing required properties: {', '.join(missing)}")
            continue
        invalid_property = False
        for key in ("id", "name", "category"):
            if not isinstance(properties.get(key), str) or not properties[key].strip():
                errors.append(f"{label}: properties.{key} must be a non-empty string")
                invalid_property = True
        if invalid_property:
            continue
        feature_id = properties.get("id")
        if isinstance(feature_id, str) and feature_id:
            if feature_id in seen_ids:
                errors.append(f"{label}: duplicate feature id {feature_id!r}")
            seen_ids.add(feature_id)

        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            errors.append(f"{label}: geometry must be a Point")
            continue
        coords = geometry.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            errors.append(f"{label}: Point coordinates must contain longitude and latitude")
            continue
        lon, lat = coords[0], coords[1]
        if (isinstance(lon, bool) or isinstance(lat, bool)
                or not isinstance(lon, (int, float)) or not isinstance(lat, (int, float))
                or not math.isfinite(lon) or not math.isfinite(lat)):
            errors.append(f"{label}: longitude and latitude must be finite numbers")
            continue
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            errors.append(f"{label}: coordinates are outside WGS84 longitude/latitude ranges")
            continue
        coordinates.append((float(lon), float(lat)))
        normalized.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {key: properties[key].strip() for key in ("id", "name", "category")},
        })

    normalized.sort(key=lambda item: item["properties"]["id"])
    bbox: list[float] | None = None
    if coordinates:
        longitudes = [pair[0] for pair in coordinates]
        latitudes = [pair[1] for pair in coordinates]
        bbox = [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]
    qa = {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "status": "failed" if errors else "passed",
        "feature_count_input": len(features),
        "feature_count_output": len(normalized) if not errors else 0,
        "geometry_types": sorted({
            feature.get("geometry", {}).get("type", "missing")
            for feature in features if isinstance(feature, dict)
            and isinstance(feature.get("geometry"), dict)
        }),
        "coordinate_reference": "OGC:CRS84 (GeoJSON longitude, latitude order)",
        "bbox": bbox,
        "checks": {
            "feature_collection": True,
            "required_properties": not any("missing required properties" in e for e in errors),
            "unique_ids": not any("duplicate feature id" in e for e in errors),
            "point_geometry": not any("geometry must be a Point" in e for e in errors),
            "finite_wgs84_coordinates": not any("coordinates" in e for e in errors),
        },
        "errors": errors,
    }
    if errors:
        return None, qa, errors
    output = {
        "type": "FeatureCollection",
        "name": "observatory-synthetic-demo",
        "bbox": bbox,
        "features": normalized,
    }
    return output, qa, []


def build(input_path: Path, output_dir: Path) -> int:
    document, raw, errors = load_geojson(input_path)
    if document is None or errors:
        qa = {
            "schema_version": 1,
            "pipeline_version": PIPELINE_VERSION,
            "status": "failed",
            "feature_count_input": None,
            "feature_count_output": 0,
            "checks": {},
            "errors": errors,
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in ("normalized.geojson", "provenance.json"):
            target = output_dir / name
            if target.exists():
                target.unlink()
        (output_dir / "qa-report.json").write_bytes(canonical_json(qa))
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1

    normalized, qa, errors = normalize(document)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "qa-report.json").write_bytes(canonical_json(qa))
    if normalized is None or errors:
        # Fail closed: no normalized data or provenance is emitted for bad input.
        for name in ("normalized.geojson", "provenance.json"):
            target = output_dir / name
            if target.exists():
                target.unlink()
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1

    normalized_bytes = canonical_json(normalized)
    provenance = {
        "schema_version": 1,
        "pipeline": "zqm-observatory-synthetic-pipeline",
        "pipeline_version": PIPELINE_VERSION,
        "input": {
            "path": input_path.name,
            "sha256": sha256_bytes(raw),
            "classification": "synthetic fixture; no external source collected",
        },
        "output": {
            "path": "normalized.geojson",
            "sha256": sha256_bytes(normalized_bytes),
        },
        "reproducibility": "Deterministic for identical input bytes and pipeline version.",
        "publication_authorized": False,
    }
    (output_dir / "normalized.geojson").write_bytes(normalized_bytes)
    (output_dir / "provenance.json").write_bytes(canonical_json(provenance))
    print(f"Pipeline passed: {len(normalized['features'])} features; publication remains unauthorized.")
    return 0



def write_draft_bundle(output_dir: Path, bundle_root: Path) -> Path:
    """Package outputs as a standards-shaped draft that remains review-blocked."""
    bundle = bundle_root / DEMO_PRODUCT_ID
    bundle.mkdir(parents=True, exist_ok=True)
    asset_names = ("normalized.geojson", "qa-report.json", "provenance.json")
    for name in asset_names:
        shutil.copyfile(output_dir / name, bundle / name)

    product = {
        "schema_version": 1,
        "product_id": DEMO_PRODUCT_ID,
        "title": "Synthetic geospatial pipeline demonstration (not for publication)",
        "publication_date": "2026-10-25",
        "geographic_scope": "Synthetic coordinates only; not a representation of Volusia County or any real place.",
        "summary": "An invented three-feature fixture used to exercise the Observatory pipeline, QA reporting, and provenance contract. It supports no real-world claims.",
        "license": "CC0 1.0 for the invented demonstration content only; no third-party source data is included.",
        "source_ids": ["observatory-synthetic-fixture"],
        "data_files": list(asset_names),
        "field_verification": {
            "status": "not_applicable",
            "notes": "All features and coordinates are synthetic; no real place or field condition is represented."
        },
        "privacy_review": {
            "reviewed": False,
            "reviewed_by": "",
            "review_date": "2026-10-25",
            "individual_level_data": False,
            "personal_data": False,
            "children_identifiable_data": False
        }
    }
    sources = [{
        "id": "observatory-synthetic-fixture",
        "title": "ZQM Observatory synthetic fixture",
        "publisher": "ZQM-Computing/zqm-observatory",
        "url": "https://github.com/ZQM-Computing/zqm-observatory/blob/main/tests/fixtures/synthetic-places.geojson",
        "retrieval_date": "2026-10-25",
        "license": "CC0 1.0 for invented fixture content; no external data collected",
        "supports": ["The invented feature attributes and coordinates used in this engineering demonstration."]
    }]
    method = """# Method

## Question and intended use

This bundle tests the Observatory's synthetic processing, validation, and provenance path. It is not a real-world geospatial product and must not support location, safety, access, or service claims.

## Inputs and processing

The only input is the repository's invented GeoJSON fixture. The pipeline checks FeatureCollection structure, required string attributes, unique IDs, Point geometries, and finite WGS84 longitude/latitude ranges. It sorts features by identifier and serializes JSON deterministically.

## Quality and provenance

The QA report records structural checks, feature counts, geometry types, and bounding box. provenance.json records SHA-256 hashes for input and normalized output. Tests exercise malformed JSON, duplicate IDs, invalid coordinates, invalid property types, deterministic output, and stale-output cleanup.

## Field verification, privacy, and rights

All data is synthetic; no external source was collected and no field conditions are represented. This draft intentionally leaves the human privacy review incomplete. The bundle must fail the publication structural gate until a reviewer records the required review. Passing pipeline checks is not publication approval.

## Reproduction and limitations

Run `python scripts/build_synthetic_product.py --output-dir build/synthetic-product --bundle-dir build/synthetic-product-bundle`. Outputs are deterministic for identical input bytes and pipeline version. This fixture does not validate real source licensing, real-world accuracy, geometry topology, or scientific suitability.
"""
    (bundle / "product.json").write_bytes(canonical_json(product))
    (bundle / "sources.json").write_bytes(canonical_json(sources))
    (bundle / "method.md").write_text(method, encoding="utf-8")
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("tests/fixtures/synthetic-places.geojson"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/synthetic-product"))
    parser.add_argument("--bundle-dir", type=Path, help="optional root directory for a standards-shaped, review-blocked draft bundle")
    args = parser.parse_args()
    result = build(args.input, args.output_dir)
    if result == 0 and args.bundle_dir is not None:
        bundle = write_draft_bundle(args.output_dir, args.bundle_dir)
        print(f"Draft product bundle created at {bundle}; publication remains blocked pending human privacy review.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
