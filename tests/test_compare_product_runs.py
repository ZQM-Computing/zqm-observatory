from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.compare_product_runs import compare


class CompareProductRunsStrictJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.before = self.root / "before.geojson"
        self.after = self.root / "after.geojson"
        feature_collection = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"id": "place-1", "name": "Example", "category": "park"},
                "geometry": {"type": "Point", "coordinates": [-80.9, 29.0]},
            }],
        }
        payload = json.dumps(feature_collection, separators=(",", ":"))
        self.before.write_text(payload, encoding="utf-8")
        self.after.write_text(payload, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_inputs_compare_successfully(self) -> None:
        report, errors = compare(self.before, self.after)
        self.assertEqual(errors, [])
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report["summary"]["unchanged_count"], 1)

    def test_duplicate_top_level_geojson_key_is_rejected(self) -> None:
        self.before.write_text(
            '{"type":"FeatureCollection","type":"FeatureCollection","features":[]}',
            encoding="utf-8",
        )
        report, errors = compare(self.before, self.after)
        self.assertIsNone(report)
        self.assertTrue(any("duplicate JSON object key: 'type'" in error for error in errors))

    def test_duplicate_feature_property_key_is_rejected(self) -> None:
        self.before.write_text(
            '{"type":"FeatureCollection","features":[{"type":"Feature",'
            '"properties":{"id":"first","id":"second","name":"Example","category":"park"},'
            '"geometry":{"type":"Point","coordinates":[-80.9,29.0]}}]}',
            encoding="utf-8",
        )
        report, errors = compare(self.before, self.after)
        self.assertIsNone(report)
        self.assertTrue(any("duplicate JSON object key: 'id'" in error for error in errors))

    def test_duplicate_review_rule_key_is_rejected(self) -> None:
        rules = self.root / "rules.json"
        rules.write_text('{"default":"low","default":"critical"}', encoding="utf-8")
        report, errors = compare(self.before, self.after, rules_path=rules)
        self.assertIsNone(report)
        self.assertTrue(any("duplicate JSON object key: 'default'" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
