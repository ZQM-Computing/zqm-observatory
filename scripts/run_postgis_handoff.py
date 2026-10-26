#!/usr/bin/env python3
"""Load the Observatory's normalized synthetic GeoJSON into disposable PostGIS.

The handoff is intentionally limited to a temporary schema in a CI-only
database. It never targets a configured production endpoint or publishes data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# Support direct execution as `python scripts/run_postgis_handoff.py`.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import psycopg
from psycopg import sql

from scripts.build_synthetic_product import build, canonical_json

SCHEMA = "observatory_handoff_ci"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_geojson(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
        raise ValueError("normalized input must be a GeoJSON FeatureCollection")
    seen: set[str] = set()
    for index, feature in enumerate(document["features"]):
        props = feature.get("properties", {})
        feature_id = props.get("id")
        coords = feature.get("geometry", {}).get("coordinates")
        if not isinstance(feature_id, str) or not feature_id or feature_id in seen:
            raise ValueError(f"feature {index}: id must be unique and non-empty")
        if not isinstance(coords, list) or len(coords) < 2:
            raise ValueError(f"feature {index}: expected Point coordinates")
        seen.add(feature_id)
    return document


def run(database_url: str, fixture: Path, output_dir: Path, producer_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir = output_dir / "normalized"
    if build(fixture, normalized_dir) != 0:
        raise RuntimeError("synthetic pipeline rejected the fixture")
    normalized_path = normalized_dir / "normalized.geojson"
    document = load_geojson(normalized_path)
    features = document["features"]
    created_schema = False
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "failed",
        "schema": SCHEMA,
        "input_sha256": sha256_bytes(normalized_path.read_bytes()),
        "feature_count_expected": len(features),
        "checks": {},
        "publication_authorized": False,
        "source_classification": "synthetic fixture; no external source collected",
    }
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                # Refuse to overwrite any existing schema. This makes cleanup
                # safe and prevents accidental collision with user objects.
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                    (SCHEMA,),
                )
                if cur.fetchone()[0]:
                    raise RuntimeError(f"refusing to reuse existing schema {SCHEMA!r}")
                cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(SCHEMA)))
                created_schema = True
                cur.execute(sql.SQL("""
                    CREATE TABLE {}.places (
                        feature_id text PRIMARY KEY,
                        name text NOT NULL,
                        category text NOT NULL,
                        geom geometry(Point, 4326) NOT NULL
                    )
                """).format(sql.Identifier(SCHEMA)))
                for feature in features:
                    props = feature["properties"]
                    lon, lat = feature["geometry"]["coordinates"][:2]
                    cur.execute(
                        sql.SQL("""
                            INSERT INTO {}.places (feature_id, name, category, geom)
                            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        """).format(sql.Identifier(SCHEMA)),
                        (props["id"], props["name"], props["category"], lon, lat),
                    )
                cur.execute(sql.SQL("SELECT count(*), count(DISTINCT feature_id), min(ST_SRID(geom)), max(ST_SRID(geom)) FROM {}.places").format(sql.Identifier(SCHEMA)))
                count, distinct_ids, min_srid, max_srid = cur.fetchone()
                cur.execute(sql.SQL("SELECT ST_XMin(ST_Extent(geom)::box3d), ST_YMin(ST_Extent(geom)::box3d), ST_XMax(ST_Extent(geom)::box3d), ST_YMax(ST_Extent(geom)::box3d) FROM {}.places").format(sql.Identifier(SCHEMA)))
                extent = list(cur.fetchone())
                expected_extent = [
                    min(f["geometry"]["coordinates"][0] for f in features),
                    min(f["geometry"]["coordinates"][1] for f in features),
                    max(f["geometry"]["coordinates"][0] for f in features),
                    max(f["geometry"]["coordinates"][1] for f in features),
                ]
                report["checks"] = {
                    "row_count_matches": count == len(features),
                    "stable_ids_unique": distinct_ids == len(features),
                    "geometry_srid_is_4326": min_srid == max_srid == 4326,
                    "extent_matches_input": all(abs(a - b) < 1e-9 for a, b in zip(extent, expected_extent)),
                }
                report["row_count"] = count
                report["distinct_id_count"] = distinct_ids
                report["srid_range"] = [min_srid, max_srid]
                report["extent"] = extent
                report["expected_extent"] = expected_extent
                if not all(report["checks"].values()):
                    raise AssertionError(f"PostGIS handoff checks failed: {report['checks']}")
                report["status"] = "passed"
    finally:
        # Only drop the schema if this run successfully created it. The target
        # is explicitly a disposable CI database, never a production database.
        if created_schema:
            with psycopg.connect(database_url) as cleanup:
                with cleanup.cursor() as cur:
                    cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(SCHEMA)))

    report["producer_commit"] = producer_commit
    report["database_layer"] = "PostGIS; synthetic disposable schema only"
    (output_dir / "handoff-report.json").write_bytes(canonical_json(report))
    manifest = {
        "schema_version": 1,
        "handoff": "observatory-synthetic-geojson-to-postgis",
        "producer_repository": "ZQM-Computing/zqm-observatory",
        "producer_commit": producer_commit,
        "fixture_path": fixture.as_posix(),
        "normalized_sha256": report["input_sha256"],
        "report_sha256": sha256_bytes(canonical_json(report)),
        "database_target": "disposable CI database; schema observatory_handoff_ci is removed after assertions",
        "publication_authorized": False,
    }
    (output_dir / "handoff-manifest.json").write_bytes(canonical_json(manifest))
    print(f"PostGIS handoff {report['status']}: {report.get('row_count', 0)} rows; publication remains unauthorized.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"), help="Disposable PostGIS connection URL (or DATABASE_URL)")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("provide --database-url or DATABASE_URL")
    try:
        report = run(args.database_url, args.fixture, args.output_dir, args.producer_commit)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
