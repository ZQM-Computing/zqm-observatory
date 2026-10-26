#!/usr/bin/env python3
"""Load a synthetic Observatory product into an explicitly disposable PostGIS database.

This is an integration-test adapter, not a production ingestion command. It
fails closed unless disposable opt-in and the exact test database are supplied.
"""
from __future__ import annotations

import hashlib
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
    source = Path(os.environ.get("OBSERVATORY_NORMALIZED_GEOJSON", "build/synthetic-product/normalized.geojson"))
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
        if not isinstance(coords, list) or len(coords) != 2:
            raise SystemExit(f"Feature {index} does not have two-dimensional Point coordinates.")
        identifier = props["id"]
        if identifier in seen:
            raise SystemExit(f"Duplicate feature id: {identifier}")
        seen.add(identifier)
        lon, lat = coords
        if isinstance(lon, bool) or isinstance(lat, bool) or not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            raise SystemExit(f"Feature {index} coordinates must be numeric.")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise SystemExit(f"Feature {index} coordinates fall outside WGS84 bounds.")
        rows.append((identifier, props["name"], props["category"], lon, lat))

    import psycopg  # Import only after fail-closed environment checks.
    conninfo = {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "dbname": database,
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
    }
    extent = None
    role_checks = {}
    with psycopg.connect(**conninfo) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                connected_db, connected_user = cur.fetchone()
                if connected_db != "observatory_test":
                    raise RuntimeError("Connected database identity did not match the disposable database guard.")
                cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
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

                # Assert an application-style read-only role boundary without
                # creating persistent roles or granting privileges outside this
                # transaction. PostgreSQL privilege predicates are authoritative.
                cur.execute("""
                    SELECT
                      EXISTS (
                        SELECT 1 FROM pg_namespace n
                        CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl, acldefault('n', n.nspowner))) a
                        WHERE n.nspname = 'observatory_handoff_test'
                          AND a.grantee = 0 AND a.privilege_type = 'USAGE'
                      ),
                      EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
                        WHERE n.nspname = 'observatory_handoff_test' AND c.relname = 'places'
                          AND a.grantee = 0 AND a.privilege_type = 'SELECT'
                      ),
                      EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
                        WHERE n.nspname = 'observatory_handoff_test' AND c.relname = 'places'
                          AND a.grantee = 0 AND a.privilege_type = 'INSERT'
                      ),
                      EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
                        WHERE n.nspname = 'observatory_handoff_test' AND c.relname = 'places'
                          AND a.grantee = 0 AND a.privilege_type = 'UPDATE'
                      ),
                      EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
                        WHERE n.nspname = 'observatory_handoff_test' AND c.relname = 'places'
                          AND a.grantee = 0 AND a.privilege_type = 'DELETE'
                      )
                """)
                public_usage, public_select, public_insert, public_update, public_delete = cur.fetchone()
                role_checks = {
                    "public_schema_usage": bool(public_usage),
                    "public_select": bool(public_select),
                    "public_insert": bool(public_insert),
                    "public_update": bool(public_update),
                    "public_delete": bool(public_delete),
                }
                if any(role_checks.values()):
                    raise AssertionError(f"Unexpected PUBLIC privileges on isolated test schema/table: {role_checks}")
        finally:
            # Ensure the synthetic schema and any extension changes made by
            # this run are not committed, including on assertion failures.
            conn.rollback()
    print(json.dumps({
        "status": "passed",
        "database_classification": "disposable test database",
        "input": source.name,
        "input_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "feature_count": len(rows),
        "srid": 4326,
        "extent": extent,
        "schema": "observatory_handoff_test",
        "role_boundary_checks": role_checks,
        "connected_database": "observatory_test",
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
