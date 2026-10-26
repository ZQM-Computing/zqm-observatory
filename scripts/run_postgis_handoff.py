#!/usr/bin/env python3
"""Load the synthetic Observatory product into a disposable PostGIS schema.

This is an integration-test adapter, not a production ingestion command. It
refuses to run unless an explicit disposable-database opt-in and database name
are supplied. It only accepts normalized GeoJSON produced by the local pipeline.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path



def main() -> int:
    if os.environ.get("OBSERVATORY_POSTGIS_DISPOSABLE") != "1":
        raise SystemExit("Refusing database writes: set OBSERVATORY_POSTGIS_DISPOSABLE=1 for a disposable test database.")
    database = os.environ.get("PGDATABASE", "")
    if database != "observatory_test":
        raise SystemExit("Refusing database writes: PGDATABASE must be exactly 'observatory_test'.")
    import psycopg  # Delayed until after safety guards so refusals work without optional dependencies.\n    source = Path(os.environ.get("OBSERVATORY_NORMALIZED_GEOJSON", "build/synthetic-product/normalized.geojson"))
    raw = source.read_bytes()
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise SystemExit("Input must be a normalized GeoJSON FeatureCollection.")
    features = document.get("features")
    if not isinstance(features, list) or not features:
        raise SystemExit("Input must contain at least one feature.")
    rows = []
    seen: set[str] = set()
    for index, feature in enumerate(features):
        props = feature.get("properties") if isinstance(feature, dict) else None
        geom = feature.get("geometry") if isinstance(feature, dict) else None
        coords = geom.get("coordinates") if isinstance(geom, dict) and geom.get("type") == "Point" else None
        if not isinstance(props, dict) or not all(isinstance(props.get(k), str) and props[k].strip() for k in ("id", "name", "category")):
            raise SystemExit(f"Feature {index} does not satisfy the normalized properties contract.")
        if not isinstance(coords, list) or len(coords) < 2:
            raise SystemExit(f"Feature {index} does not have Point coordinates.")
        identifier = props["id"]
        if identifier in seen:
            raise SystemExit(f"Duplicate feature id: {identifier}")
        seen.add(identifier)
        lon, lat = coords[0], coords[1]
        if isinstance(lon, bool) or isinstance(lat, bool) or not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            raise SystemExit(f"Feature {index} coordinates must be numeric.")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise SystemExit(f"Feature {index} coordinates fall outside WGS84 bounds.")
        rows.append((identifier, props["name"], props["category"], lon, lat))

    conninfo = {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "dbname": database,
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
    }
    with psycopg.connect(**conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            # This schema is intentionally dedicated to the integration test.
            cur.execute("DROP SCHEMA IF EXISTS observatory_handoff_test CASCADE")
            cur.execute("CREATE SCHEMA observatory_handoff_test")
            cur.execute(
                "CREATE TABLE observatory_handoff_test.places ("
                "id text PRIMARY KEY, name text NOT NULL, category text NOT NULL, "
                "geom geometry(Point, 4326) NOT NULL)"
            )
            cur.executemany(
                "INSERT INTO observatory_handoff_test.places (id, name, category, geom) "
                "VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
                rows,
            )
            cur.execute("SELECT count(*), count(DISTINCT id), min(ST_SRID(geom)), max(ST_SRID(geom)) FROM observatory_handoff_test.places")
            count, unique_count, min_srid, max_srid = cur.fetchone()
            if count != len(rows) or unique_count != len(rows) or min_srid != 4326 or max_srid != 4326:
                raise AssertionError(f"PostGIS handoff mismatch: count={count}, unique={unique_count}, SRID={min_srid}..{max_srid}")
            cur.execute("SELECT min(ST_X(geom)), min(ST_Y(geom)), max(ST_X(geom)), max(ST_Y(geom)) FROM observatory_handoff_test.places")
            extent = cur.fetchone()
            if any(value is None for value in extent):
                raise AssertionError("PostGIS extent unexpectedly empty.")
            cur.execute("SELECT id, name, category FROM observatory_handoff_test.places ORDER BY id")
            actual = cur.fetchall()
            expected = sorted((identifier, name, category) for identifier, name, category, _, _ in rows)
            if actual != expected:
                raise AssertionError("PostGIS attributes differ from the normalized GeoJSON input.")
            # Integration fixture is deliberately ephemeral: rollback all schema
            # changes so repeated runs leave the disposable DB unchanged.
            conn.rollback()
    print(json.dumps({
        "status": "passed",
        "database_classification": "disposable test database",
        "input": source.name,
        "input_bytes_sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "feature_count": len(rows),
        "srid": 4326,
        "extent": extent,
        "schema": "observatory_handoff_test",
        "writes_committed": False,
        "publication_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
