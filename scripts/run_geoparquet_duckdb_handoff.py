#!/usr/bin/env python3
"""Convert a local synthetic GeoJSON fixture to GeoParquet and validate it with DuckDB Spatial.

The pipeline reads only local files, does not overwrite the fixture, and emits
machine-readable aggregate QA and provenance. DuckDB's Spatial extension must
already be available to the runtime (CI provisions it separately).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

EXPECTED_CATEGORIES = {"park": 1, "public-space": 1, "library": 1}
EXPECTED_EXTENT = [-81.2, 29.0, -81.0, 29.2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def validate_source(path: Path) -> tuple[int, list[str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if not isinstance(value, dict) or value.get("type") != "FeatureCollection":
        raise ValueError("fixture must be a GeoJSON FeatureCollection")
    features = value.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("fixture must contain a non-empty features array")
    seen: set[str] = set()
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            errors.append(f"feature {index} must be a GeoJSON Feature")
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            errors.append(f"feature {index} requires properties")
            continue
        for field in ("id", "name", "category"):
            field_value = properties.get(field)
            if not isinstance(field_value, str) or not field_value.strip():
                errors.append(f"feature {index} requires non-empty string {field}")
        identifier = properties.get("id")
        if isinstance(identifier, str) and identifier in seen:
            errors.append(f"duplicate stable id: {identifier}")
        elif isinstance(identifier, str):
            seen.add(identifier)
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            errors.append(f"feature {index} must have Point geometry")
            continue
        coordinates = geometry.get("coordinates")
        if (not isinstance(coordinates, list) or len(coordinates) != 2
                or any(not isinstance(number, (int, float)) or isinstance(number, bool) for number in coordinates)):
            errors.append(f"feature {index} must have two numeric coordinates")
            continue
        x, y = coordinates
        if not (-180 <= x <= 180 and -90 <= y <= 90):
            errors.append(f"feature {index} coordinates fall outside EPSG:4326 bounds")
    if errors:
        raise ValueError("; ".join(errors))
    return len(features), sorted(seen)


def inspect_geoparquet(path: Path, expected_count: int) -> dict[str, Any]:
    import pyarrow.parquet as pq
    import geopandas as gpd
    from pyproj import CRS

    table = pq.read_table(path)
    metadata = table.schema.metadata or {}
    if b"geo" not in metadata:
        raise ValueError("GeoParquet metadata key 'geo' is missing")
    geo = json.loads(metadata[b"geo"].decode("utf-8"))
    primary = geo.get("primary_column")
    columns = geo.get("columns", {})
    if not isinstance(primary, str) or primary not in columns:
        raise ValueError("GeoParquet primary geometry column is missing from metadata")
    geometry_meta = columns[primary]
    if geometry_meta.get("encoding") != "WKB":
        raise ValueError("GeoParquet geometry encoding must be WKB")
    if "Point" not in geometry_meta.get("geometry_types", []):
        raise ValueError("GeoParquet metadata must declare Point geometry")
    crs_meta = geometry_meta.get("crs")
    if crs_meta is None:
        raise ValueError("GeoParquet geometry CRS metadata is missing")
    if CRS.from_json_dict(crs_meta).to_epsg() != 4326:
        raise ValueError("GeoParquet CRS metadata must resolve to EPSG:4326")
    if table.num_rows != expected_count:
        raise ValueError(f"GeoParquet row count {table.num_rows} != expected {expected_count}")
    frame = gpd.read_parquet(path)
    if frame.crs is None or frame.crs.to_epsg() != 4326:
        raise ValueError("GeoPandas round-trip CRS must resolve to EPSG:4326")
    if frame.geometry.name != primary:
        raise ValueError("GeoPandas geometry column does not match GeoParquet primary column")
    if not frame.geometry.is_valid.all() or frame.geometry.is_empty.any():
        raise ValueError("GeoParquet round-trip contains invalid or empty geometry")
    return {
        "rows": int(table.num_rows),
        "columns": table.column_names,
        "primary_geometry_column": primary,
        "geometry_encoding": geometry_meta["encoding"],
        "geometry_types": sorted(geometry_meta["geometry_types"]),
        "crs_epsg": 4326,
        "geo_metadata_version": geo.get("version"),
    }


def query_with_duckdb(path: Path) -> dict[str, Any]:
    import duckdb

    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("LOAD spatial")
        # Keep geometry decoding explicit so this check exercises GeoParquet WKB.
        query = """
            WITH decoded AS (
                SELECT id, name, category, ST_GeomFromWKB(geometry) AS geom
                FROM read_parquet(?)
            )
            SELECT
                COUNT(*) AS feature_count,
                COUNT(DISTINCT id) AS unique_ids,
                COUNT(*) FILTER (WHERE id IS NULL OR trim(id) = '') AS invalid_ids,
                COUNT(*) FILTER (WHERE name IS NULL OR trim(name) = '') AS invalid_names,
                COUNT(*) FILTER (WHERE category IS NULL OR trim(category) = '') AS invalid_categories,
                COUNT(*) FILTER (WHERE NOT ST_IsValid(geom) OR ST_IsEmpty(geom)) AS invalid_geometries,
                COUNT(*) FILTER (WHERE ST_GeometryType(geom) <> 'POINT') AS non_point_geometries,
                MIN(ST_X(geom)) AS min_x,
                MIN(ST_Y(geom)) AS min_y,
                MAX(ST_X(geom)) AS max_x,
                MAX(ST_Y(geom)) AS max_y
            FROM decoded
        """
        row = connection.execute(query, [path.as_posix()]).fetchone()
        category_rows = connection.execute(
            "SELECT category, COUNT(*) AS n FROM read_parquet(?) GROUP BY category ORDER BY category",
            [path.as_posix()],
        ).fetchall()
        if row is None:
            raise ValueError("DuckDB query returned no aggregate row")
        return {
            "duckdb_version": duckdb.__version__,
            "feature_count": int(row[0]),
            "unique_ids": int(row[1]),
            "invalid_ids": int(row[2]),
            "invalid_names": int(row[3]),
            "invalid_categories": int(row[4]),
            "invalid_geometries": int(row[5]),
            "non_point_geometries": int(row[6]),
            "extent": [float(row[7]), float(row[8]), float(row[9]), float(row[10])],
            "category_counts": {str(category): int(count) for category, count in category_rows},
        }
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True, help="Local synthetic GeoJSON fixture")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for GeoParquet and QA evidence")
    parser.add_argument("--geoparquet-commit", required=True, help="Pinned geoparquet-cookbook commit SHA")
    parser.add_argument("--duckdb-commit", required=True, help="Pinned duckdb-spatial-cookbook commit SHA")
    args = parser.parse_args(argv)

    fixture = args.fixture.resolve()
    output_dir = args.output_dir.resolve()
    for label, commit in (("geoparquet", args.geoparquet_commit), ("duckdb", args.duckdb_commit)):
        if len(commit) < 7 or any(char not in "0123456789abcdef" for char in commit.lower()):
            parser.error(f"--{label}-commit must be a hexadecimal commit identifier of at least 7 characters")
    if not fixture.is_file():
        parser.error(f"fixture does not exist: {fixture}")
    if output_dir == fixture.parent or fixture.parent in output_dir.parents:
        parser.error("output directory must not be inside the fixture directory")

    try:
        input_hash_before = sha256_file(fixture)
        feature_count, stable_ids = validate_source(fixture)
        import geopandas as gpd

        frame = gpd.read_file(fixture)
        if frame.crs is None or frame.crs.to_epsg() != 4326:
            raise ValueError("source GeoJSON must resolve to EPSG:4326")
        if frame.geometry.name != "geometry":
            frame = frame.rename_geometry("geometry")
        # GeoParquet cookbook's documented GeoPandas write/read pattern, applied
        # to the Observatory's pinned local fixture rather than cookbook sample data.
        output_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = output_dir / "synthetic-places.parquet"
        frame.to_parquet(parquet_path, index=False)
        format_report = inspect_geoparquet(parquet_path, feature_count)
        analytics = query_with_duckdb(parquet_path)
        expected = {
            "feature_count": feature_count,
            "unique_ids": len(stable_ids),
            "invalid_ids": 0,
            "invalid_names": 0,
            "invalid_categories": 0,
            "invalid_geometries": 0,
            "non_point_geometries": 0,
            "extent": EXPECTED_EXTENT,
            "category_counts": EXPECTED_CATEGORIES,
        }
        mismatches = {
            key: {"expected": value, "observed": analytics.get(key)}
            for key, value in expected.items()
            if analytics.get(key) != value
        }
        if mismatches:
            raise ValueError("DuckDB results differ from fixture contract: " + json.dumps(mismatches, sort_keys=True))
        if sha256_file(fixture) != input_hash_before:
            raise ValueError("input fixture changed during handoff")
        report = {
            "schema_version": 1,
            "status": "passed",
            "fixture": fixture.name,
            "fixture_sha256": input_hash_before,
            "feature_ids": stable_ids,
            "input_crs": "EPSG:4326",
            "format_validation": format_report,
            "duckdb_aggregate_qa": analytics,
            "expected_values_match": True,
            "input_unchanged": True,
        }
        report_path = output_dir / "geoparquet-duckdb-qa.json"
        report_path.write_bytes(canonical_json(report))
        manifest = {
            "schema_version": 1,
            "pipeline": "observatory-geoparquet-duckdb-handoff",
            "producer_repositories": {
                "geoparquet_cookbook": {
                    "repository": "ZQM-Computing/geoparquet-cookbook",
                    "commit": args.geoparquet_commit.lower(),
                    "pattern": "GeoPandas GeoParquet write/read and metadata inspection",
                },
                "duckdb_spatial_cookbook": {
                    "repository": "ZQM-Computing/duckdb-spatial-cookbook",
                    "commit": args.duckdb_commit.lower(),
                    "pattern": "DuckDB Spatial GeoParquet read and expected-value assertions",
                },
            },
            "runtime": {
                "python": platform.python_version(),
                "geopandas": gpd.__version__,
                "duckdb": analytics["duckdb_version"],
            },
            "inputs": [{"path": fixture.name, "sha256": input_hash_before}],
            "outputs": [
                {"path": parquet_path.name, "sha256": sha256_file(parquet_path)},
                {"path": report_path.name, "sha256": sha256_file(report_path)},
            ],
            "decision": "technical_qa_passed_not_release_authorization",
            "source_rights_approved": False,
            "privacy_review_approved": False,
            "human_release_review_approved": False,
            "notes": [
                "Only the repository's synthetic fixture was processed.",
                "DuckDB Spatial must be provisioned before execution; extension download is an environment setup concern, not part of data processing.",
                "A successful format and analytical QA handoff does not establish rights to publish any real-world source data.",
            ],
        }
        manifest_path = output_dir / "handoff-manifest.json"
        manifest_path.write_bytes(canonical_json(manifest))
        print(f"GeoParquet/DuckDB handoff verified: {manifest_path}")
        print(f"Fixture SHA-256: {input_hash_before}")
        print(f"GeoParquet SHA-256: {sha256_file(parquet_path)}")
        print(f"QA report SHA-256: {sha256_file(report_path)}")
        return 0
    except Exception as exc:
        print(f"GeoParquet/DuckDB handoff failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
