from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_geoparquet_duckdb_handoff import canonical_json, sha256_file, validate_source


class GeoParquetDuckDBHandoffTests(unittest.TestCase):
    def test_accepts_synthetic_fixture_and_returns_sorted_stable_ids(self):
        fixture = Path(__file__).parent / "fixtures" / "synthetic-places.geojson"
        count, identifiers = validate_source(fixture)
        self.assertEqual(count, 3)
        self.assertEqual(identifiers, ["place-001", "place-002", "place-003"])

    def test_rejects_duplicate_ids_and_non_point_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.geojson"
            feature = {
                "type": "Feature",
                "properties": {"id": "same", "name": "Example", "category": "park"},
                "geometry": {"type": "Point", "coordinates": [-81.0, 29.0]},
            }
            fixture.write_text(json.dumps({"type": "FeatureCollection", "features": [feature, feature]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate stable id"):
                validate_source(fixture)
            feature["geometry"] = {"type": "LineString", "coordinates": [[-81.0, 29.0], [-81.1, 29.1]]}
            fixture.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Point geometry"):
                validate_source(fixture)

    def test_rejects_out_of_range_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.geojson"
            fixture.write_text(json.dumps({"type": "FeatureCollection", "features": [{
                "type": "Feature",
                "properties": {"id": "x", "name": "Example", "category": "park"},
                "geometry": {"type": "Point", "coordinates": [200, 95]},
            }]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside EPSG:4326 bounds"):
                validate_source(fixture)

    def test_canonical_json_is_stable_and_hash_tracks_file_bytes(self):
        payload = {"z": 1, "a": ["x", "y"]}
        self.assertEqual(canonical_json(payload), canonical_json(payload))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            path.write_bytes(canonical_json(payload))
            self.assertEqual(sha256_file(path), sha256_file(path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)


if __name__ == "__main__":
    unittest.main()
