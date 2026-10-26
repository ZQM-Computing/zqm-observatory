from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_postgis_handoff import load_fixture, validate_aggregate


class PostgisHandoffContractTests(unittest.TestCase):
    def _write(self, directory: str, value: object) -> Path:
        path = Path(directory) / "fixture.geojson"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_loads_valid_point_fixture_and_calculates_expected_aggregates(self):
        fixture = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"id": "b", "name": "Beta", "category": "park"},
                 "geometry": {"type": "Point", "coordinates": [-81.1, 29.2]}},
                {"type": "Feature", "properties": {"id": "a", "name": "Alpha", "category": "library"},
                 "geometry": {"type": "Point", "coordinates": [-81.2, 29.0]}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, fixture)
            features, expected = load_fixture(path)
        self.assertEqual([feature["id"] for feature in features], ["a", "b"])
        self.assertEqual(expected["feature_count"], 2)
        self.assertEqual(expected["unique_ids"], 2)
        self.assertEqual(expected["extent"], [-81.2, 29.0, -81.1, 29.2])
        self.assertEqual(expected["category_counts"], {"library": 1, "park": 1})

    def test_rejects_duplicate_ids_bad_geometry_and_out_of_range_coordinates(self):
        cases = [
            {"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"id": "x", "name": "A", "category": "park"},
                 "geometry": {"type": "Point", "coordinates": [0, 0]}},
                {"type": "Feature", "properties": {"id": "x", "name": "B", "category": "park"},
                 "geometry": {"type": "Point", "coordinates": [1, 1]}},
            ]},
            {"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"id": "x", "name": "A", "category": "park"},
                 "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}},
            ]},
            {"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"id": "x", "name": "A", "category": "park"},
                 "geometry": {"type": "Point", "coordinates": [181, 0]}},
            ]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for index, value in enumerate(cases):
                with self.subTest(case=index):
                    path = Path(tmp) / f"fixture-{index}.geojson"
                    path.write_text(json.dumps(value), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_fixture(path)

    def test_aggregate_validator_rejects_wrong_counts_extent_and_categories(self):
        expected = {
            "feature_count": 2,
            "unique_ids": 2,
            "invalid_attributes": 0,
            "invalid_geometries": 0,
            "crs_epsg": 4326,
            "extent": [-81.2, 29.0, -81.1, 29.2],
            "category_counts": {"library": 1, "park": 1},
        }
        actual = dict(expected)
        self.assertEqual(validate_aggregate(actual, expected), [])
        actual["feature_count"] = 3
        actual["extent"] = [-81.2, 29.0, -80.0, 29.2]
        actual["category_counts"] = {"park": 2}
        errors = validate_aggregate(actual, expected)
        self.assertTrue(any("feature_count mismatch" in item for item in errors))
        self.assertTrue(any("extent mismatch" in item for item in errors))
        self.assertTrue(any("category_counts mismatch" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
