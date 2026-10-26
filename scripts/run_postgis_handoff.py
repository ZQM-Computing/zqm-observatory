#!/usr/bin/env python3
"""Load the synthetic Observatory fixture into disposable PostGIS and run a pinned cookbook RLS pattern.

This adapter is a CI handoff, not a production loader. It refuses existing
fixture schemas/roles, uses only a synthetic GeoJSON fixture, and records a
machine-readable report with publication authorization explicitly false.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

COOKBOOK_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
DEMO_ROLES = (
    "postgis_cb_north_ops",
    "postgis_cb_coastal_ops",
    "postgis_cb_read_all_geo",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def load_fixture(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate the small synthetic Point fixture and calculate expected aggregates."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("type") != "FeatureCollection":
        raise ValueError("fixture must be a GeoJSON FeatureCollection")
    features = value.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("fixture must contain at least one feature")

    seen: set[str] = set()
    categories: dict[str, int] = {}
    coordinates: list[tuple[float, float]] = []
    normalized: list[dict[str, Any]] = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"feature {index} must be a GeoJSON Feature")
        props = feature.get("properties")
        if not isinstance(props, dict):
            raise ValueError(f"feature {index} must have a properties object")
        for key in ("id", "name", "category"):
            item = props.get(key)
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"feature {index} requires non-empty string properties.{key}")
        if props["id"] in seen:
            raise ValueError(f"duplicate feature id: {props['id']}")
        seen.add(props["id"])

        geom = feature.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") != "Point":
            raise ValueError(f"feature {index} must have Point geometry")
        coords = geom.get("coordinates")
        if (
            not isinstance(coords, list)
            or len(coords) != 2
            or any(not isinstance(n, (int, float)) or isinstance(n, bool) for n in coords)
        ):
            raise ValueError(f"feature {index} coordinates must be two numeric values")
        x, y = float(coords[0]), float(coords[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(f"feature {index} coordinates must be finite")
        if not (-180 <= x <= 180 and -90 <= y <= 90):
            raise ValueError(f"feature {index} coordinates fall outside EPSG:4326 bounds")
        coordinates.append((x, y))
        categories[props["category"]] = categories.get(props["category"], 0) + 1
        normalized.append({"id": props["id"], "name": props["name"], "category": props["category"], "x": x, "y": y})

    normalized.sort(key=lambda item: item["id"])
    xs, ys = [item[0] for item in coordinates], [item[1] for item in coordinates]
    expected = {
        "feature_count": len(normalized),
        "unique_ids": len(seen),
        "invalid_attributes": 0,
        "invalid_geometries": 0,
        "crs_epsg": 4326,
        "extent": [min(xs), min(ys), max(xs), max(ys)],
        "category_counts": dict(sorted(categories.items())),
    }
    return normalized, expected


def validate_aggregate(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("feature_count", "unique_ids", "invalid_attributes", "invalid_geometries", "crs_epsg", "category_counts"):
        if actual.get(key) != expected.get(key):
            errors.append(f"{key} mismatch: expected {expected.get(key)!r}, received {actual.get(key)!r}")
    actual_extent = actual.get("extent")
    expected_extent = expected.get("extent")
    if not isinstance(actual_extent, list) or len(actual_extent) != 4:
        errors.append("extent must contain four coordinates")
    elif not isinstance(expected_extent, list) or len(expected_extent) != 4:
        errors.append("expected extent must contain four coordinates")
    elif any(not isinstance(a, (int, float)) or not math.isclose(float(a), float(e), rel_tol=0, abs_tol=1e-9) for a, e in zip(actual_extent, expected_extent)):
        errors.append(f"extent mismatch: expected {expected_extent!r}, received {actual_extent!r}")
    return errors


def connect_database():
    import psycopg

    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
    )


def run_psql_file(path: Path, env: dict[str, str]) -> str:
    result = subprocess.run(
        ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-f", str(path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        # Keep SQL stdout/stderr for diagnostics, but never print the connection environment.
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"pinned PostGIS cookbook SQL failed ({path.name}): {detail[-3000:]}")
    return result.stdout


def run_handoff(fixture: Path, output_dir: Path, cookbook_dir: Path, cookbook_commit: str) -> dict[str, Any]:
    normalized, expected = load_fixture(fixture)
    input_hash_before = sha256_file(fixture)
    sql_paths = [
        cookbook_dir / "sql/00_extensions_and_schema.sql",
        cookbook_dir / "sql/01_sample_data.sql",
        cookbook_dir / "patterns/07_row_level_security.sql",
    ]
    for path in sql_paths:
        if not path.is_file():
            raise FileNotFoundError(f"required pinned cookbook SQL file is missing: {path}")

    env = os.environ.copy()
    required_env = ("PGDATABASE", "PGUSER", "PGPASSWORD")
    missing = [key for key in required_env if not env.get(key)]
    if missing:
        raise ValueError("missing database environment variables: " + ", ".join(missing))
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGPORT", "5432")

    import psycopg

    with connect_database() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'patterns'")
            if cur.fetchone():
                raise RuntimeError("refusing to reuse pre-existing role 'patterns'; use a fresh disposable database")
            cur.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'observatory_ci'")
            if cur.fetchone():
                raise RuntimeError("refusing to reuse pre-existing schema 'observatory_ci'; use a fresh disposable database")
            cur.execute("CREATE ROLE patterns NOLOGIN")
            cur.execute("CREATE SCHEMA observatory_ci")
            cur.execute(
                "CREATE TABLE observatory_ci.places ("
                "id text PRIMARY KEY, name text NOT NULL, category text NOT NULL, "
                "geom geometry(Point, 4326) NOT NULL)"
            )
            for item in normalized:
                cur.execute(
                    "INSERT INTO observatory_ci.places (id, name, category, geom) "
                    "VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
                    (item["id"], item["name"], item["category"], item["x"], item["y"]),
                )

    sql_outputs = [run_psql_file(path, env) for path in sql_paths]
    if "Pattern 07 (spatial row-level security) completed and cleaned up" not in sql_outputs[-1]:
        raise RuntimeError("pinned cookbook RLS pattern did not emit its successful cleanup marker")

    with connect_database() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::integer,
                    COUNT(DISTINCT id)::integer,
                    COUNT(*) FILTER (WHERE id IS NULL OR btrim(id) = '' OR btrim(name) = '' OR btrim(category) = '')::integer,
                    COUNT(*) FILTER (WHERE geom IS NULL OR ST_IsEmpty(geom) OR NOT ST_IsValid(geom) OR GeometryType(geom) <> 'POINT')::integer,
                    COUNT(DISTINCT ST_SRID(geom))::integer,
                    MIN(ST_X(geom)), MIN(ST_Y(geom)), MAX(ST_X(geom)), MAX(ST_Y(geom))
                FROM observatory_ci.places
                """
            )
            row = cur.fetchone()
            actual = {
                "feature_count": int(row[0]),
                "unique_ids": int(row[1]),
                "invalid_attributes": int(row[2]),
                "invalid_geometries": int(row[3]),
                "crs_epsg": 4326 if int(row[4]) == 1 else None,
                "extent": [float(v) for v in row[5:9]],
            }
            cur.execute("SELECT category, COUNT(*)::integer FROM observatory_ci.places GROUP BY category ORDER BY category")
            actual["category_counts"] = {str(category): int(count) for category, count in cur.fetchall()}
            cur.execute("SELECT COUNT(*)::integer FROM demo.service_areas")
            service_areas = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*)::integer FROM demo.service_sites")
            service_sites = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*)::integer FROM demo.parcels")
            parcels = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*)::integer FROM demo.sensor_observations")
            observations = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*)::integer FROM pg_roles WHERE rolname = ANY(%s)",
                [list(DEMO_ROLES)],
            )
            remaining_demo_roles = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*)::integer FROM pg_policies WHERE schemaname = 'demo' AND policyname LIKE 'postgis_cb_%'"
            )
            remaining_demo_policies = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COALESCE(bool_or(relrowsecurity OR relforcerowsecurity), false) "
                "FROM pg_class WHERE oid IN ('demo.service_sites'::regclass, 'demo.parcels'::regclass)"
            )
            rls_still_enabled = bool(cur.fetchone()[0])
            cur.execute("SELECT postgis_full_version()")
            postgis_version = str(cur.fetchone()[0])

    errors = validate_aggregate(actual, expected)
    if (service_areas, service_sites, parcels, observations) != (3, 9, 24, 27):
        errors.append("cookbook synthetic demo counts changed; expected (3 areas, 9 sites, 24 parcels, 27 observations)")
    if remaining_demo_roles != 0 or remaining_demo_policies != 0 or rls_still_enabled:
        errors.append("cookbook RLS pattern did not fully clean up demo roles/policies/table flags")
    input_hash_after = sha256_file(fixture)
    if input_hash_after != input_hash_before:
        errors.append("synthetic fixture changed during PostGIS handoff")
    if errors:
        raise AssertionError("; ".join(errors))

    report = {
        "schema_version": 1,
        "handoff": "zqm-observatory-postgis-cookbook",
        "decision": "technical_qa_passed_pending_independent_release_gates",
        "publication_authorized": False,
        "source_rights_approved": False,
        "privacy_review_approved": False,
        "fixture": {
            "path": fixture.name,
            "sha256_before": input_hash_before,
            "sha256_after": input_hash_after,
            "feature_count": expected["feature_count"],
        },
        "producer": {
            "repository": "ZQM-Computing/postgis-cookbook",
            "commit": cookbook_commit,
            "pattern": "patterns/07_row_level_security.sql",
        },
        "runtime": {
            "postgis_full_version": postgis_version,
            "crs_epsg": actual["crs_epsg"],
        },
        "observatory_fixture_qa": actual,
        "cookbook_rls_demo": {
            "service_areas": service_areas,
            "service_sites": service_sites,
            "parcels": parcels,
            "sensor_observations": observations,
            "demo_roles_remaining": remaining_demo_roles,
            "demo_policies_remaining": remaining_demo_policies,
            "rls_flags_remaining": rls_still_enabled,
        },
        "checks": {
            "fixture_loaded_and_aggregates_match": True,
            "pinned_cookbook_rls_pattern_completed": True,
            "cookbook_fixture_counts_match": True,
            "rls_demo_cleanup_verified": True,
            "input_unchanged": True,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "postgis-handoff-report.json").write_bytes(canonical_json(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cookbook-dir", type=Path, required=True)
    parser.add_argument("--cookbook-commit", required=True)
    args = parser.parse_args(argv)
    if not COOKBOOK_COMMIT_RE.fullmatch(args.cookbook_commit):
        parser.error("--cookbook-commit must be a hexadecimal commit SHA")
    fixture = args.fixture.resolve()
    cookbook_dir = args.cookbook_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not fixture.is_file():
        parser.error(f"fixture does not exist: {fixture}")
    if not cookbook_dir.is_dir():
        parser.error(f"cookbook checkout does not exist: {cookbook_dir}")
    if output_dir == fixture.parent or fixture.parent in output_dir.parents:
        parser.error("output directory must not be inside the fixture directory")
    try:
        report = run_handoff(fixture, output_dir, cookbook_dir, args.cookbook_commit)
    except (OSError, ValueError, RuntimeError, AssertionError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "PostGIS handoff passed: "
        f"{report['fixture']['feature_count']} Observatory fixture features verified; "
        "pinned RLS pattern executed and cleaned up; publication remains unauthorized."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
